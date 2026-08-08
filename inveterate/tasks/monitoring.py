from celery import shared_task
from celery_singleton import Singleton
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from ..models import Service, ServiceNetwork
from ..proxmox import get_proxmox_connection
from ._common import logger
from .control import get_cluster, get_vm


def get_vm_osinfo(service_id):
    """Get OS info from QEMU guest agent. Returns None for LXC or if agent unavailable."""
    machine, service = get_vm(service_id)
    if service.service_plan.type != "kvm":
        return None
    try:
        proxmox = get_proxmox_connection(service.node.cluster)
        node = proxmox.nodes(service.node)
        response = node.qemu(service.machine_id).agent("get-osinfo").get()
        result = response.get("result", {})
        return {
            "name": result.get("name", ""),
            "version": result.get("version", ""),
            "kernel_release": result.get("kernel-release", ""),
            "kernel_version": result.get("kernel-version", ""),
            "machine": result.get("machine", ""),
        }
    except Exception:
        logger.debug("Guest agent OS info unavailable for service %s", service_id)
        return None


@shared_task(name="inveterate.tasks.get_vm_status", base=Singleton, lock_expiry=60 * 15)
def get_vm_status(service_id):
    machine, service = get_vm(service_id)
    vm_stats = machine.status.current.get()
    disk = vm_stats.get("disk", 0)
    maxdisk = vm_stats.get("maxdisk", 0)

    # For KVM, Proxmox returns disk=0 in status/current.
    # Try guest agent first, then fall back to storage volume allocation.
    if service.service_plan.type == "kvm" and disk == 0:
        proxmox = get_proxmox_connection(service.node.cluster)
        node = proxmox.nodes(service.node)

        # Try guest agent for filesystem-level usage (most accurate)
        if vm_stats.get("status") == "running":
            try:
                fs_info = node.qemu(service.machine_id).agent("get-fsinfo").get()
                total_used = 0
                total_size = 0
                for fs in fs_info.get("result", []):
                    total_used += fs.get("used-bytes", 0)
                    total_size += fs.get("total-bytes", 0)
                if total_size > 0:
                    disk = total_used
                    maxdisk = total_size
            except Exception:
                logger.debug("Guest agent unavailable for service %s", service_id)

        # Fall back to storage volume allocation (thin-provisioned actual usage)
        if disk == 0:
            try:
                config = node.qemu(service.machine_id).config.get()
                for key in ("scsi0", "virtio0", "ide0", "sata0"):
                    val = config.get(key, "")
                    if val and ":" in val.split(",")[0]:
                        storage_name, vol_name = val.split(",")[0].split(":", 1)
                        vol_id = f"{storage_name}:{vol_name}"
                        vol_info = node.storage(storage_name).content(vol_id).get()
                        if vol_info.get("used", 0) > 0:
                            disk = vol_info["used"]
                            maxdisk = vol_info.get("size", maxdisk)
                        break
            except Exception:
                logger.debug("Storage query unavailable for service %s, using Proxmox defaults", service_id)

    stats = {
        "status": vm_stats["status"],
        "cpu": vm_stats.get("cpu", 0),
        "mem": vm_stats.get("mem", 0),
        "maxmem": vm_stats.get("maxmem", 0),
        "disk": disk,
        "maxdisk": maxdisk,
        "uptime": vm_stats.get("uptime", 0),
        "netin": vm_stats.get("netin", 0),
        "netout": vm_stats.get("netout", 0),
    }
    return stats


def get_vm_ips(service_id):
    networks = (
        ServiceNetwork.objects.filter(service_id=service_id)
        .select_related("ip__pool")
        .prefetch_related("port_block__gateway", "port_block__forwards")
    )
    ips = []
    for network in networks:
        ip = {
            "value": network.ip.value,
            "primary": network.net_id == 0,
            "pool": {
                "type": network.ip.pool.type,
                "internal": network.ip.pool.internal,
            },
        }
        if network.ip.pool.internal and hasattr(network, "port_block"):
            pb = network.port_block
            ip["port_block"] = {
                "gateway_host": pb.gateway.host,
                "gateway_name": pb.gateway.name,
                "port_start": pb.port_start,
                "port_end": pb.port_end,
                "forwards": [
                    {
                        "external_port": pf.external_port,
                        "internal_port": pf.internal_port,
                        "protocol": pf.protocol,
                        "label": pf.label,
                        "enabled": pf.enabled,
                    }
                    for pf in pb.forwards.all()
                ],
            }
        ips.append(ip)
    return ips


@shared_task(name="inveterate.tasks.get_cluster_resources", base=Singleton, lock_expiry=60 * 15)
def get_cluster_resources(pk=None, query_type="node"):
    cluster = get_cluster(cluster_id=pk)
    if query_type == "vm":
        stats = []
        vms = cluster.resources.get(type=query_type)
        for vm in vms:
            if "pool" in vm and vm["pool"] == "inveterate":
                stats.append(vm)
    elif query_type == "storage":
        stats = []
        disks = cluster.resources.get(type=query_type)
        for disk in disks:
            content = disk["content"].split(",")
            if "rootdir" in content:
                stats.append(disk)
    else:
        stats = cluster.resources.get(type=query_type)
    return stats


@shared_task(
    name="inveterate.tasks.suspend_service",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError,),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def suspend_service(service_id):
    logger.info("Suspending service %s", service_id)
    machine, service = get_vm(service_id)
    machine.status.suspend.post(todisk=1)
    service.status = "suspended"
    service.save()


@shared_task(
    name="inveterate.tasks.reinstate_service",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError,),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def reinstate_service(service_id):
    logger.info("Reinstating service %s", service_id)
    machine, service = get_vm(service_id)
    machine.status.start.post()
    service.status = "active"
    service.save()


@shared_task(name="inveterate.tasks.meter_bandwidth", base=Singleton, lock_expiry=60 * 15)
def meter_bandwidth():
    logger.info("Starting bandwidth metering")
    api_objects = {}
    services_to_update = []
    now = timezone.now()

    # Optimize query with select_related to avoid N+1 queries
    services = Service.objects.filter(status="active").select_related("node", "node__cluster", "service_plan")

    services_processed = 0
    services_failed = 0

    for service in services:
        try:
            # Skip if no bandwidth tracking
            if not service.bw_renewal_dtm:
                logger.debug("Service %s has no bandwidth tracking, skipping", service.id)
                continue

            node_name = service.node.name
            if node_name not in api_objects:
                api_objects[node_name] = get_proxmox_connection(service.node.cluster)
            node = api_objects[node_name].nodes(node_name)

            # Handle bandwidth renewal
            if now > service.bw_renewal_dtm:
                service.bw_renewal_dtm = now + relativedelta(months=1)
                # Rebaseline the live counter for the new period: bw_stale is the
                # already-accounted baseline of bw_usage (see the restart branch,
                # which banks bw_usage - bw_stale). Assign (not +=) so it tracks the
                # current counter; += accumulates old baselines across unattended
                # renewals and drives bw_banked negative on the next restart.
                service.bw_stale = service.bw_usage
                service.bw_banked = 0
                logger.info("Renewed bandwidth for service %s", service.id)

            # Get VM stats
            if service.service_plan.type == "lxc":
                machine = node.lxc(service.machine_id)
            elif service.service_plan.type == "kvm":
                machine = node.qemu(service.machine_id)
            else:
                logger.warning("Unknown service type %s for service %s", service.service_plan.type, service.id)
                continue

            data = machine.status.current.get()
            tick = data["uptime"]

            if tick > service.bw_system_tick:
                try:
                    service.bw_usage = data["netin"] + data["netout"]
                except KeyError as e:
                    logger.warning("Missing network data for service %s: %s", service.id, e)
            elif tick < service.bw_system_tick:
                # VM was restarted
                banked = service.bw_usage - service.bw_stale
                service.bw_banked += banked
                service.bw_usage = 0
                service.bw_stale = 0
                try:
                    service.bw_usage = data["netin"] + data["netout"]
                except KeyError as e:
                    logger.warning("Missing network data for service %s: %s", service.id, e)

            service.bw_system_tick = tick
            services_to_update.append(service)
            services_processed += 1

        except ResourceException as e:
            logger.error("Proxmox API error for service %s: %s", service.id, e)
            services_failed += 1
        except Exception as e:
            logger.error("Failed to meter bandwidth for service %s: %s", service.id, e, exc_info=True)
            services_failed += 1

    # Bulk update all service bandwidth records
    if services_to_update:
        Service.objects.bulk_update(
            services_to_update, ["bw_usage", "bw_stale", "bw_banked", "bw_system_tick", "bw_renewal_dtm"]
        )
        logger.info(
            "Bandwidth metering completed: %s services processed, %s failed, %s updated",
            services_processed, services_failed, len(services_to_update),
        )
    else:
        logger.info("No bandwidth data to update")
