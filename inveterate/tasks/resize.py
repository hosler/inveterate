"""Mechanical VM resize.

This module is a pure executor. Given a service and a target Plan it stops the
VM, applies the new CPU/RAM/disk to Proxmox, updates the ServicePlan snapshot,
and restarts it. All eligibility and billing policy (disk-shrink rules, app
minimums, proration, status gating, etc.) is enforced upstream in nascent before
``resize_service`` is enqueued. The only guard here is the *physical* one:
Proxmox cannot shrink a disk.
"""

import time

from celery import shared_task
from celery_singleton import Singleton
from requests.exceptions import ConnectionError

from ..models import Plan, Service
from ..proxmox import get_proxmox_connection
from ._common import MAX_POLL_SECONDS, logger

# PlanBase resource fields copied from a Plan into the Service's ServicePlan snapshot.
_PLAN_SPEC_FIELDS = (
    "size",
    "ram",
    "swap",
    "cores",
    "bandwidth",
    "cpu_units",
    "cpu_limit",
    "ipv4_ips",
    "ipv6_ips",
    "internal_ips",
)


# How long to wait for a graceful (ACPI) shutdown before forcing a hard stop.
# Keeps resize downtime bounded when the guest agent isn't responsive.
GRACEFUL_SHUTDOWN_SECONDS = 60


def _wait_for_machine(machine, service_id, label="", status=None, timeout=MAX_POLL_SECONDS):
    """Poll until the VM is unlocked (and optionally in ``status``)."""
    poll_start = time.monotonic()
    while True:
        if time.monotonic() - poll_start > timeout:
            raise TimeoutError(f"Wait ({label}) timed out after {timeout}s for service {service_id}")
        current = machine.status.current.get()
        if "lock" not in current and (status is None or current.get("status") == status):
            return
        time.sleep(2)


def _wait_for_task(node, upid, service_id, label=""):
    """Poll a Proxmox task UPID until it completes successfully."""
    poll_start = time.monotonic()
    while True:
        if time.monotonic() - poll_start > MAX_POLL_SECONDS:
            raise TimeoutError(f"Task wait ({label}) timed out after {MAX_POLL_SECONDS}s for service {service_id}")
        task = node.tasks(upid).status.get()
        if task.get("status") == "stopped":
            if task.get("exitstatus") != "OK":
                raise RuntimeError(
                    f"Proxmox task {label} failed for service {service_id}: {task.get('exitstatus')}"
                )
            return
        time.sleep(2)


def _run_task(node, upid, service_id, label):
    """Wait for a Proxmox async operation when it returned a task UPID."""
    if upid:
        _wait_for_task(node, upid, service_id, label)


@shared_task(
    name="inveterate.tasks.resize_service",
    base=Singleton,
    unique_on=["service_id"],
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError,),
    retry_backoff=10,
    retry_backoff_max=120,
    max_retries=3,
)
def resize_service(service_id, target_plan_id):
    """Resize a service's VM to a target plan's resource spec (stop -> apply -> start).

    The Singleton lock keys on ``service_id`` only (``unique_on``) so two resize
    calls with *different* target plans for the same service can no longer run
    concurrently and race the ServicePlan snapshot against the real VM.

    ``operation_in_progress`` is atomically claimed by the dispatching viewset
    before this task is enqueued (see nascent ``service_change_plan``); the
    finally block guarantees it is cleared even if the resize raises.
    """
    Service.objects.filter(pk=service_id).update(operation_in_progress=True)
    try:
        service = Service.objects.select_related("service_plan", "node", "node__cluster").get(pk=service_id)
        sp = service.service_plan
        target_plan = Plan.objects.get(pk=target_plan_id)

        if sp is None or not service.machine_id:
            raise ValueError(f"Service {service_id} is not provisioned; cannot resize.")
        if target_plan.size < sp.size:
            # Proxmox cannot shrink a disk; refuse rather than issue an invalid resize.
            raise ValueError(f"Cannot shrink disk from {sp.size}GB to {target_plan.size}GB for service {service_id}.")

        vm_type = sp.type
        grow_disk = target_plan.size > sp.size
        proxmox = get_proxmox_connection(service.node.cluster, timeout=600)
        node = proxmox.nodes(service.node)
        machine = node.qemu(service.machine_id) if vm_type == "kvm" else node.lxc(service.machine_id)

        was_running = machine.status.current.get().get("status") == "running"
        Service.objects.filter(pk=service_id).update(status_msg="Resizing")
        logger.info("Resizing service %s (%s) to plan %s", service_id, vm_type, target_plan_id)

        try:
            if was_running:
                upid = machine.status.shutdown.post()
                try:
                    _run_task(node, upid, service_id, "shutdown")
                    _wait_for_machine(
                        machine, service_id, "shutdown", status="stopped", timeout=GRACEFUL_SHUTDOWN_SECONDS
                    )
                except TimeoutError:
                    logger.warning("Graceful shutdown timed out for service %s, forcing stop", service_id)
                    upid = machine.status.stop.post()
                    _run_task(node, upid, service_id, "force-stop")
                    _wait_for_machine(machine, service_id, "force-stop", status="stopped")

            if vm_type == "kvm":
                upid = machine.config.post(
                    memory=target_plan.ram, vcpus=target_plan.cores, cores=target_plan.cores
                )
                _run_task(node, upid, service_id, "resize-config")
                _wait_for_machine(machine, service_id, "resize-config")
                applied_fields = ("ram", "cores")
            else:
                upid = machine.config.put(memory=target_plan.ram, cores=target_plan.cores, swap=target_plan.swap)
                _run_task(node, upid, service_id, "resize-config")
                _wait_for_machine(machine, service_id, "resize-config")
                applied_fields = ("ram", "cores", "swap")

            # Checkpoint only the resources confirmed applied. If disk growth
            # fails, inventory still reflects the CPU/RAM now present on the VM.
            for field in applied_fields:
                setattr(sp, field, getattr(target_plan, field))
            sp.save(update_fields=applied_fields)

            if grow_disk:
                disk = "scsi0" if vm_type == "kvm" else "rootfs"
                upid = machine.resize.put(disk=disk, size=f"{target_plan.size}G")
                _run_task(node, upid, service_id, "resize-disk")
                _wait_for_machine(machine, service_id, "resize-disk")
                sp.size = target_plan.size
                sp.save(update_fields=("size",))

            # The remaining plan attributes become current only after all
            # machine-side resize steps have succeeded.
            for field in _PLAN_SPEC_FIELDS:
                setattr(sp, field, getattr(target_plan, field))
            sp.name = target_plan.name
            sp.save()

            if was_running:
                upid = machine.status.start.post()
                _run_task(node, upid, service_id, "start")
                _wait_for_machine(machine, service_id, "start", status="running")
        except Exception as e:
            logger.error("Failed to resize service %s: %s", service_id, e, exc_info=True)
            Service.objects.filter(pk=service_id).update(status="error", status_msg=f"Resize failed: {e}"[:255])
            if was_running:
                try:
                    upid = machine.status.start.post()
                    _run_task(node, upid, service_id, "recovery-start")
                    _wait_for_machine(machine, service_id, "recovery-start", status="running")
                except Exception:
                    logger.warning("Could not restart service %s after failed resize", service_id, exc_info=True)
            raise

        Service.objects.filter(pk=service_id).update(status_msg=None)
        logger.info("Resized service %s to plan %s", service_id, target_plan_id)

        # Recompute available inventory now that this service's footprint changed.
        import inveterate.tasks as _tasks

        _tasks.calculate_inventory.delay()
    except Exception as e:
        # This also covers connection creation and the initial status lookup,
        # including a VM that was removed manually from Proxmox.
        Service.objects.filter(pk=service_id).update(status="error", status_msg=f"Resize failed: {e}"[:255])
        raise
    finally:
        Service.objects.filter(pk=service_id).update(operation_in_progress=False)
