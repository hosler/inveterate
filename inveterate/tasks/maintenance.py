from celery import shared_task
from celery_singleton import Singleton
from django.conf import settings
from django.db.models import Sum
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from ..models import (
    IP,
    Cluster,
    Inventory,
    IPPool,
    Node,
    Plan,
    Service,
    ServiceNetwork,
)
from ..proxmox import get_proxmox_connection, is_console_user, is_legacy_console_user
from ._common import delete_snippet, logger, write_snippet


@shared_task(name="inveterate.tasks.calculate_inventory", base=Singleton, lock_expiry=60 * 15)
def calculate_inventory():
    logger.info("Starting inventory calculation")
    plans = Plan.objects.all()
    nodes = Node.objects.all()
    # Optional allowlist (e.g. dev limits provisioning to Ceph-capable nodes).
    # Default unset = all nodes, so prod behaviour is unchanged.
    allowed_nodes = getattr(settings, "INVETERATE_INVENTORY_NODES", None)
    if allowed_nodes:
        nodes = nodes.filter(name__in=allowed_nodes)
        # Zero out excluded nodes so node selection never lands on them.
        Inventory.objects.exclude(node__name__in=allowed_nodes).update(quantity=0)
    inventory_fields = ["cores", "ram"]

    # Precompute per-node resource usage in a single query
    node_usage = {}
    for row in (
        Service.objects.exclude(status="destroyed")
        .values("node_id")
        .annotate(
            total_cores=Sum("service_plan__cores"),
            total_ram=Sum("service_plan__ram"),
            total_size=Sum("service_plan__size"),
        )
    ):
        node_usage[row["node_id"]] = row

    # Precompute shared disk usage by storage name (avoids N+1 in the plan loop)
    shared_disk_usage = {}
    for row in (
        Service.objects.filter(
            service_plan__storage__shared=True,
        )
        .exclude(status="destroyed")
        .values("service_plan__storage__name")
        .annotate(total=Sum("service_plan__size"))
    ):
        shared_disk_usage[row["service_plan__storage__name"]] = row["total"] or 0

    for node in nodes:
        usage = node_usage.get(node.id, {})
        for plan in plans:
            lowest = None
            for field in inventory_fields:
                services_value = usage.get(f"total_{field}") or 0
                node_value = getattr(node, field)
                plan_value = getattr(plan, field)
                try:
                    quantity = int((node_value - services_value) / plan_value)
                except ZeroDivisionError:
                    quantity = float("inf")
                if lowest is None or quantity < lowest:
                    lowest = quantity

            # Disk accounting: use primary disk, fall back to largest
            primary_disk = node.node_disk.filter(primary=True).first()
            if not primary_disk:
                primary_disk = node.node_disk.order_by("-size").first()
            if primary_disk and plan.size > 0:
                if primary_disk.shared:
                    disk_used = shared_disk_usage.get(primary_disk.name, 0)
                else:
                    disk_used = usage.get("total_size") or 0
                disk_slots = int((primary_disk.size - disk_used) / plan.size)
                if lowest is None or disk_slots < lowest:
                    lowest = disk_slots

            # IP accounting: check available IPs in pools assigned to this node
            node_pools = IPPool.objects.filter(nodes=node)
            for ip_type, plan_field in [("internal", "internal_ips"), ("ipv4", "ipv4_ips"), ("ipv6", "ipv6_ips")]:
                needed = getattr(plan, plan_field)
                if needed <= 0:
                    continue
                if ip_type == "internal":
                    pools = node_pools.filter(internal=True)
                else:
                    pools = node_pools.filter(internal=False, type=ip_type)
                free_ips = IP.objects.filter(pool__in=pools, owner__isnull=True).count()
                ip_slots = int(free_ips / needed)
                if lowest is None or ip_slots < lowest:
                    lowest = ip_slots

            inventory, created = Inventory.objects.get_or_create(plan=plan, node=node)
            inventory.quantity = lowest if lowest is not None else 0
            inventory.save()
            logger.debug("Node %s, Plan %s: %s slots available", node.name, plan.name, inventory.quantity)

    # Cluster-level bandwidth cap
    for cluster in Cluster.objects.all():
        if cluster.bandwidth <= 0:
            continue
        cluster_nodes = nodes.filter(cluster=cluster)
        bw_used = (
            Service.objects.filter(node__cluster=cluster)
            .exclude(status="destroyed")
            .aggregate(total=Sum("service_plan__bandwidth"))["total"]
            or 0
        )
        bw_remaining = cluster.bandwidth - bw_used

        for plan in plans:
            if plan.bandwidth <= 0:
                continue
            bw_slots = max(0, int(bw_remaining / plan.bandwidth))
            # Cap each node's inventory for this plan by the cluster bandwidth limit
            for node in cluster_nodes:
                try:
                    inv = Inventory.objects.get(plan=plan, node=node)
                    if inv.quantity > bw_slots:
                        inv.quantity = bw_slots
                        inv.save()
                        logger.debug("Node %s, Plan %s: capped to %s by cluster bandwidth", node.name, plan.name, bw_slots)
                except Inventory.DoesNotExist:
                    pass

    logger.info("Inventory calculation completed")


@shared_task(
    name="inveterate.tasks.cancel_service",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError,),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def cancel_service(service_id):
    logger.info("Cancelling service %s", service_id)
    # Import via the package so that tests can patch ``inveterate.tasks.delete_npm_*``
    import inveterate.tasks as _tasks

    from .control import get_vm

    delete_npm_stream = _tasks.delete_npm_stream
    delete_npm_proxy_host = _tasks.delete_npm_proxy_host

    service = Service.objects.get(pk=service_id)
    if service.status == "destroyed":
        logger.warning("Service %s is already destroyed, skipping cancellation", service_id)
        return

    machine, service = get_vm(service_id)

    # The VM may already be gone (e.g. deleted manually in Proxmox). Treat a
    # missing VM as already-deleted and fall through to the DB-side teardown so
    # the service isn't stranded in the database with its IPs still allocated.
    vm_exists = True
    try:
        machine.status.current.get()
    except ResourceException:
        vm_exists = False
        logger.warning("VM for service %s not found on Proxmox; skipping VM delete", service_id)

    if vm_exists:
        if service.service_plan.type == "lxc":
            machine.delete(force=1)
        else:
            # KVM delete doesn't support force — stop the VM first if running
            try:
                status = machine.status.current.get()
                if status.get("status") == "running":
                    machine.status.stop.post()
                    import time

                    from ._common import MAX_POLL_SECONDS

                    poll_start = time.monotonic()
                    while True:
                        if time.monotonic() - poll_start > MAX_POLL_SECONDS:
                            raise TimeoutError(f"Stop timed out for service {service_id}")
                        s = machine.status.current.get()
                        if s.get("status") == "stopped":
                            break
                        time.sleep(2)
            except ResourceException:
                pass
            machine.delete()

    # Clean up cloud-init snippet if one was written
    if service.service_plan and service.service_plan.type == "kvm" and service.machine_id and service.node:
        try:
            proxmox = get_proxmox_connection(service.node.cluster)
            delete_snippet(proxmox, service.node.name, f"ci-{service.machine_id}.yml")
        except Exception:
            logger.warning("Failed to delete cloud-init snippet for service %s", service_id, exc_info=True)

    # Collect NPM cleanup info before deleting ServiceNetwork records
    npm_streams_to_delete = []
    npm_proxy_hosts_to_delete = []

    for sn in service.service_network.all():
        if hasattr(sn, "port_block"):
            gateway_id = sn.port_block.gateway_id
            for pf in sn.port_block.forwards.filter(npm_stream_id__isnull=False):
                npm_streams_to_delete.append((gateway_id, pf.npm_stream_id))

    # Collect domain route NPM proxy hosts
    internal_sn = service.service_network.filter(ip__pool__internal=True).first()
    if internal_sn and hasattr(internal_sn, "port_block"):
        gateway_id = internal_sn.port_block.gateway_id
        for dr in service.domain_routes.filter(npm_proxy_host_id__isnull=False):
            npm_proxy_hosts_to_delete.append((gateway_id, dr.npm_proxy_host_id))

    # Release IPs back to the pool by deleting ServiceNetwork records.
    # IP.owner is a OneToOneField with on_delete=SET_NULL, so deleting
    # the ServiceNetwork automatically sets IP.owner = NULL.
    service.service_network.all().delete()

    # Fire async NPM cleanup tasks after data is safely collected
    for gateway_id, npm_stream_id in npm_streams_to_delete:
        delete_npm_stream.delay(gateway_id, npm_stream_id)
    for gateway_id, npm_proxy_host_id in npm_proxy_hosts_to_delete:
        delete_npm_proxy_host.delay(gateway_id, npm_proxy_host_id)

    service.status = "destroyed"
    service.save()


@shared_task(name="inveterate.tasks.cleanup_orphaned_ips", base=Singleton, lock_expiry=60 * 15)
def cleanup_orphaned_ips():
    """
    Safety-net task to release IPs orphaned by past bugs or edge cases.
    Finds ServiceNetwork records belonging to destroyed services and deletes
    them, which auto-nulls IP.owner via the SET_NULL cascade.
    """
    logger.info("Starting orphaned IP cleanup")
    orphaned = ServiceNetwork.objects.filter(service__status="destroyed")
    count = orphaned.count()
    if count:
        orphaned.delete()
        logger.info("Cleaned up %s orphaned ServiceNetwork records", count)
    else:
        logger.info("No orphaned IPs found")


@shared_task(name="inveterate.tasks.cleanup_stale_error_services", base=Singleton, lock_expiry=60 * 15)
def cleanup_stale_error_services():
    """Mark services stuck in 'error' status for over 24 hours as destroyed.

    Error services consume inventory slots indefinitely. This task reclaims
    capacity by destroying services that failed provisioning and were never
    retried or resolved.
    """
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(hours=24)
    stale = Service.objects.filter(status="error", updated__lt=cutoff)
    count = stale.count()
    if count:
        stale.update(status="destroyed", status_msg="Auto-destroyed: stuck in error state")
        logger.info("Destroyed %d stale error services (older than 24h)", count)
    else:
        logger.info("No stale error services found")


@shared_task(name="inveterate.tasks.cleanup_console_users", base=Singleton, lock_expiry=60 * 15)
def cleanup_console_users():
    """
    Clean up orphaned Proxmox console users.

    Current format: ``inv-s{service_id}@pve`` (per-service).
    Also cleans up legacy ``inveterate{owner_id}@pve`` users left over from
    the previous per-owner naming scheme.
    """

    logger.info("Starting console user cleanup")

    active_service_ids = set(Service.objects.exclude(status="destroyed").values_list("id", flat=True))
    # Legacy fallback: owners who still have active services
    active_owner_ids = set(Service.objects.exclude(status="destroyed").values_list("owner_id", flat=True).distinct())

    cleaned_up = 0
    errors = 0

    for cluster in Cluster.objects.all():
        try:
            proxmox = get_proxmox_connection(cluster)
            users = proxmox.access.users.get()

            for user in users:
                userid = user.get("userid", "")

                # Per-service users (current format)
                service_id = is_console_user(userid)
                if service_id is not None:
                    if service_id not in active_service_ids:
                        proxmox.access.users(userid).delete()
                        logger.info("Deleted orphaned console user: %s", userid)
                        cleaned_up += 1
                    continue

                # Legacy per-owner users (transitional cleanup)
                owner_id = is_legacy_console_user(userid)
                if owner_id is not None:
                    if owner_id not in active_owner_ids:
                        proxmox.access.users(userid).delete()
                        logger.info("Deleted legacy console user: %s", userid)
                        cleaned_up += 1

        except ConnectionError as e:
            logger.error("Cannot connect to cluster %s: %s", cluster.name, e)
            errors += 1
        except ResourceException as e:
            logger.error("Proxmox API error on cluster %s: %s", cluster.name, e)
            errors += 1
        except Exception as e:
            logger.error("Failed to cleanup console users on cluster %s: %s", cluster.name, e, exc_info=True)
            errors += 1

    logger.info("Console user cleanup completed: %s users removed, %s clusters with errors", cleaned_up, errors)


@shared_task(
    name="inveterate.tasks.update_service_ssh_keys",
    autoretry_for=(ConnectionError,),
    retry_backoff=5,
    retry_backoff_max=60,
    max_retries=3,
)
def update_service_ssh_keys(service_id, ssh_keys):
    """Update SSH authorized keys on a KVM service via cloud-init snippet."""
    import urllib.parse

    from .provisioning import _SSH_KEY_PREFIXES, _compose_cloud_init

    logger.info("Updating SSH keys for service %s", service_id)
    service = Service.objects.get(pk=service_id)

    if service.service_plan.type != "kvm":
        logger.warning("SSH key update not supported for LXC service %s", service_id)
        return

    valid_keys = [k for k in ssh_keys if any(k.startswith(p) for p in _SSH_KEY_PREFIXES)]
    if not valid_keys:
        logger.warning("No valid SSH keys provided for service %s", service_id)
        return

    try:
        proxmox = get_proxmox_connection(service.node.cluster)
        node = proxmox.nodes(service.node)
        machine = node.qemu(service.machine_id)

        # Set SSH keys in VM config (used when cicustom is not set)
        encoded_keys = urllib.parse.quote("\n".join(valid_keys), safe="")
        machine.config.post(sshkeys=encoded_keys)
        logger.info("Set %s SSH key(s) in VM config for service %s", len(valid_keys), service_id)

        # Regenerate cloud-init snippet with app profiles + SSH keys.
        # When cicustom is set it replaces auto-generated user-data entirely,
        # so we must include the user directive for keys to apply correctly.
        ciuser = service.owner.email.split("@")[0]
        snippet_name = f"ci-{service.machine_id}.yml"
        ci_content = _compose_cloud_init(
            service.service_plan.apps.all(),
            ssh_keys=valid_keys,
            user=ciuser,
            hostname=service.hostname,
            kvm=True,
        )
        if ci_content:
            write_snippet(proxmox, service.node.name, snippet_name, ci_content)
            machine.config.post(cicustom=f"user=local:snippets/{snippet_name}")
        logger.info("Updated cloud-init snippet for service %s", service_id)

        # Regenerate cloud-init drive and reboot to apply
        machine.cloudinit.put()
        logger.info("Regenerated cloud-init drive for service %s", service_id)

        logger.warning("Rebooting service %s to apply SSH key changes", service_id)
        machine.status.reboot.post()
        logger.info("Rebooted service %s to apply SSH key changes", service_id)
    except Exception as e:
        Service.objects.filter(pk=service_id).update(status_msg=f"SSH key update failed: {e}")
        raise
