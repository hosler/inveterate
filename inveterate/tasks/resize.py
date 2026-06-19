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


@shared_task(
    name="inveterate.tasks.resize_service",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError,),
    retry_backoff=10,
    retry_backoff_max=120,
    max_retries=3,
)
def resize_service(service_id, target_plan_id):
    """Resize a service's VM to a target plan's resource spec (stop -> apply -> start)."""
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
            machine.status.shutdown.post()
            try:
                _wait_for_machine(machine, service_id, "shutdown", status="stopped", timeout=GRACEFUL_SHUTDOWN_SECONDS)
            except TimeoutError:
                logger.warning("Graceful shutdown timed out for service %s, forcing stop", service_id)
                machine.status.stop.post()
                _wait_for_machine(machine, service_id, "force-stop", status="stopped")

        if vm_type == "kvm":
            machine.config.post(memory=target_plan.ram, vcpus=target_plan.cores, cores=target_plan.cores)
            _wait_for_machine(machine, service_id, "resize-config")
            if grow_disk:
                machine.resize.put(disk="scsi0", size=f"{target_plan.size}G")
        else:
            machine.config.put(memory=target_plan.ram, cores=target_plan.cores, swap=target_plan.swap)
            if grow_disk:
                machine.resize.put(disk="rootfs", size=f"{target_plan.size}G")

        # Update the snapshot to reflect the new spec.
        for field in _PLAN_SPEC_FIELDS:
            setattr(sp, field, getattr(target_plan, field))
        sp.name = target_plan.name
        sp.save()

        if was_running:
            machine.status.start.post()
    except Exception as e:
        logger.error("Failed to resize service %s: %s", service_id, e, exc_info=True)
        Service.objects.filter(pk=service_id).update(status_msg=f"Resize failed: {e}"[:255])
        if was_running:
            try:
                machine.status.start.post()
            except Exception:
                logger.warning("Could not restart service %s after failed resize", service_id)
        raise

    Service.objects.filter(pk=service_id).update(status_msg=None)
    logger.info("Resized service %s to plan %s", service_id, target_plan_id)

    # Recompute available inventory now that this service's footprint changed.
    import inveterate.tasks as _tasks

    _tasks.calculate_inventory.delay()
