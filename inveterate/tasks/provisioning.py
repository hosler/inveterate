import time
from io import BytesIO

import yaml
from celery import shared_task
from celery_singleton import Singleton
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from ..models import IP, IPPool, NodeDisk, PortBlock, PortGateway, Service, ServiceNetwork
from ..proxmox import get_proxmox_connection
from ._common import MAX_POLL_SECONDS, logger

_SSH_KEY_PREFIXES = (
    "ssh-rsa ",
    "ssh-ed25519 ",
    "ssh-dss ",
    "ecdsa-sha2-",
    "sk-ssh-ed25519@openssh.com ",
    "sk-ecdsa-sha2-",
)


def _compose_cloud_init(apps, ssh_keys=None):
    """Merge AppProfile cloud_init fragments into a single cloud-config document.

    Args:
        apps: QuerySet of AppProfile objects to merge.
        ssh_keys: Optional list of SSH public key strings to inject via cloud-init.
    """
    merged_keys = ("packages", "runcmd", "write_files")
    merged = {}
    for app in apps.order_by("pk"):
        fragment = yaml.safe_load(app.cloud_init)
        if not isinstance(fragment, dict):
            continue
        for key in merged_keys:
            if key in fragment:
                value = fragment[key]
                if not isinstance(value, list):
                    logger.warning("AppProfile %s has non-list value for '%s', skipping", app.pk, key)
                    continue
                merged.setdefault(key, []).extend(value)
    if ssh_keys:
        valid_keys = [k for k in ssh_keys if any(k.startswith(p) for p in _SSH_KEY_PREFIXES)]
        if len(valid_keys) != len(ssh_keys):
            logger.warning("Filtered %d invalid SSH keys from cloud-init", len(ssh_keys) - len(valid_keys))
        if valid_keys:
            merged["ssh_authorized_keys"] = valid_keys
    if not merged:
        return ""
    return "#cloud-config\n" + yaml.dump(merged, default_flow_style=False)


@shared_task(name="inveterate.tasks.assign_ips", base=Singleton, lock_expiry=60 * 15)
def assign_ips(service_id):
    logger.info(f"Assigning IPs for service {service_id}")
    service = Service.objects.get(pk=service_id)
    service_plan = service.service_plan
    internal_ips = service_plan.internal_ips
    ipv4_ips = service_plan.ipv4_ips
    ipv6_ips = service_plan.ipv6_ips
    ips = IP.objects.filter(owner__service=service).all()
    for ip in ips:
        if ip.pool.internal is True:
            internal_ips -= 1
        elif ip.pool.type == "ipv4":
            ipv4_ips -= 1
        elif ip.pool.type == "ipv6":
            ipv6_ips -= 1
    ip_pools = IPPool.objects.filter(nodes=service.node).all()

    def _allocate_ip(pool_filter, label):
        """Try to allocate one IP matching pool_filter.

        Returns True on success, False if no matching pools exist (config gap),
        raises RuntimeError if matching pools exist but are exhausted.
        """
        matching_pools = [p for p in ip_pools if pool_filter(p)]
        if not matching_pools:
            return False
        for pool in matching_pools:
            with transaction.atomic():
                ip = IP.objects.select_for_update(skip_locked=True).filter(owner=None, pool=pool).first()
                if ip:
                    service_network = ServiceNetwork.objects.create(service=service)
                    ip.owner = service_network
                    ip.save()
                    return True
        raise RuntimeError(f"All {label} IP pools exhausted for service {service_id}")

    with transaction.atomic():
        for i in range(internal_ips):
            if not _allocate_ip(lambda p: p.internal is True, "internal"):
                logger.warning("No internal IP pools configured for node %s (service %s)", service.node, service_id)
        for i in range(ipv4_ips):
            if not _allocate_ip(lambda p: p.type == "ipv4" and p.internal is not True, "IPv4"):
                logger.warning("No IPv4 IP pools configured for node %s (service %s)", service.node, service_id)
        for i in range(ipv6_ips):
            if not _allocate_ip(lambda p: p.type == "ipv6" and p.internal is not True, "IPv6"):
                logger.warning("No IPv6 IP pools configured for node %s (service %s)", service.node, service_id)

    # Allocate port blocks for internal IPs that don't have one yet
    internal_networks = (
        ServiceNetwork.objects.filter(service=service, ip__pool__internal=True)
        .select_related("ip__pool")
        .exclude(port_block__isnull=False)
    )

    for sn in internal_networks:
        gateways = PortGateway.objects.filter(pools=sn.ip.pool)
        for gw in gateways:
            with transaction.atomic():
                # Lock gateway's port blocks to find next available slot
                existing_starts = set(
                    PortBlock.objects.select_for_update().filter(gateway=gw).values_list("port_start", flat=True)
                )
                port = gw.port_range_start
                allocated = False
                while port + gw.block_size - 1 <= gw.port_range_end:
                    if port not in existing_starts:
                        PortBlock.objects.create(
                            gateway=gw,
                            service_network=sn,
                            port_start=port,
                            port_end=port + gw.block_size - 1,
                        )
                        logger.info(
                            f"Allocated port block {port}-{port + gw.block_size - 1} on {gw.name} for service {service_id}"
                        )
                        allocated = True
                        break
                    port += gw.block_size
                if not allocated:
                    logger.warning(f"No available port block on gateway {gw.name} for service {service_id}")


@shared_task(name="inveterate.tasks.provision_service", base=Singleton, lock_expiry=60 * 15)
def provision_service(service_id, password, ssh_keys=None):
    logger.info(f"Starting provisioning for service {service_id}")
    service = Service.objects.get(pk=service_id)

    # Idempotency guard: skip if already provisioned
    if service.status == "active":
        logger.warning(f"Service {service_id} is already active, skipping provisioning")
        return

    logger.info(f"Provisioning {service.service_plan.type} service '{service.hostname}' on node {service.node.name}")

    proxmox = get_proxmox_connection(service.node.cluster, timeout=600)
    node = proxmox.nodes(service.node)
    service_type = service.service_plan.type
    try:
        proxmox.pools.post(poolid="inveterate")
        logger.debug("Created or verified 'inveterate' pool exists")
    except ResourceException:
        pass

    # If you got no storage you get some storage
    if not service.service_plan.storage:
        service.service_plan.storage = NodeDisk.objects.get(node=service.node, primary=True)

    # Generate machine_id, avoiding collisions with both cluster VMIDs
    # and machine_ids already assigned to other services (prevents races).
    if not service.machine_id:
        with transaction.atomic():
            locked_svc = Service.objects.select_for_update().get(pk=service_id)
            if not locked_svc.machine_id:
                candidate = int(f"1{locked_svc.id:06}")
                existing_vmids = {r["vmid"] for r in proxmox.cluster.resources.get(type="vm")}
                existing_vmids.update(Service.objects.exclude(machine_id=None).values_list("machine_id", flat=True))
                while candidate in existing_vmids:
                    candidate += 1
                locked_svc.machine_id = candidate
                locked_svc.save(update_fields=["machine_id"])
            service.machine_id = locked_svc.machine_id
    try:
        logger.debug(f"Assigning IPs for service {service_id}")
        assign_ips(service_id)
        logger.debug(f"IP assignment completed for service {service_id}")

        if service_type == "kvm":
            # Find which node has the template
            clone_node = node
            template_vmid = int(service.service_plan.template.file)
            for resource in proxmox.cluster.resources.get(type="vm"):
                if resource["vmid"] == template_vmid:
                    clone_node = proxmox.nodes(resource["node"])
                    break

            # Cross-node clone requires shared storage; use it as
            # intermediate then move to the target disk if needed.
            target_storage = service.service_plan.storage.name
            clone_storage = target_storage
            cross_node = clone_node is not node
            if cross_node:
                shared_disk = NodeDisk.objects.filter(node=service.node, shared=True).first()
                if shared_disk:
                    clone_storage = shared_disk.name

            clone_data = {
                "newid": service.machine_id,
                "storage": clone_storage,
                "full": 1,
                "target": service.node.name,
            }
            try:
                clone_node.qemu(service.service_plan.template.file).clone.post(**clone_data)
                # Wait for clone to finish (check both source and target
                # nodes since the VM may briefly live on the source).
                locked = True
                poll_start = time.monotonic()
                while locked:
                    if time.monotonic() - poll_start > MAX_POLL_SECONDS:
                        raise TimeoutError(
                            f"Clone lock poll timed out after {MAX_POLL_SECONDS}s for service {service_id}"
                        )
                    time.sleep(2)
                    for check_node in (node, clone_node):
                        try:
                            status = check_node.qemu(service.machine_id).status.current.get()
                            if "lock" not in status:
                                locked = False
                            break
                        except ResourceException:
                            continue
                # For cross-node clones, wait until the VM actually
                # appears on the target node (migration after clone).
                if cross_node:
                    poll_start = time.monotonic()
                    while True:
                        if time.monotonic() - poll_start > MAX_POLL_SECONDS:
                            raise TimeoutError(
                                f"Cross-node migration poll timed out after {MAX_POLL_SECONDS}s for service {service_id}"
                            )
                        try:
                            node.qemu(service.machine_id).status.current.get()
                            break
                        except ResourceException:
                            time.sleep(2)
            except ResourceException as e:
                if "config file already exists" in str(e):
                    pass
                else:
                    raise

            vm_data = {
                "onboot": 1,
                "memory": service.service_plan.ram,
                "vcpus": service.service_plan.cores,
                "cores": service.service_plan.cores,
                "balloon": 0,
                "name": service.hostname,
                "ciuser": service.owner,
            }
            if password is not None:
                vm_data["cipassword"] = password

            # Compose and upload cloud-init snippet for app profiles and/or SSH keys
            if service.service_plan.apps.exists() or ssh_keys:
                ci_content = _compose_cloud_init(service.service_plan.apps.all(), ssh_keys=ssh_keys)
                if ci_content:
                    snippet_name = f"ci-{service.machine_id}.yml"
                    node.storage("local").upload.post(
                        content="snippets",
                        filename=snippet_name,
                        file=BytesIO(ci_content.encode()),
                    )
                    vm_data["cicustom"] = f"user=local:snippets/{snippet_name}"

        if service_type == "lxc":
            vm_data = {
                "ostemplate": f"local:vztmpl/{service.service_plan.template.file}",
                "hostname": service.hostname,
                "storage": service.service_plan.storage.name,
                "memory": service.service_plan.ram,
                "swap": service.service_plan.swap,
                "cores": service.service_plan.cores,
                "rootfs": f"{service.service_plan.storage.name}:{service.service_plan.size}",
                "password": password,
                "unprivileged": "1",
                "onboot": "1",
                "start": "1",
                "searchdomain": service.hostname,
                "pool": "inveterate",
            }

        # Build network configuration from assigned IPs
        for network in service.service_network.all():
            firewall = 0
            if network.ip.pool.internal is True:
                firewall = 1
            net_data = {
                "bridge": network.ip.pool.interface,
                "firewall": firewall,
            }
            if network.ip.pool.vlan_tag:
                net_data["tag"] = network.ip.pool.vlan_tag
            if service_type == "kvm":
                net_data["model"] = "virtio"
                if network.ip.pool.type == "ipv4":
                    vm_data[f"ipconfig{network.net_id}"] = (
                        f"ip={network.ip.value}/{network.ip.pool.mask},gw={network.ip.pool.gateway}"
                    )
                else:
                    vm_data[f"ipconfig{network.net_id}"] = (
                        f"ip6={network.ip.value}/{network.ip.pool.mask},gw6={network.ip.pool.gateway}"
                    )
            if service_type == "lxc":
                net_data["name"] = f"eth{network.net_id}"
                if network.ip.pool.type == "ipv4":
                    net_data["ip"] = f"{network.ip.value}/{network.ip.pool.mask}"
                    net_data["gw"] = f"{network.ip.pool.gateway}"
                else:
                    net_data["ip6"] = f"{network.ip.value}/{network.ip.pool.mask}"
                    net_data["gw6"] = f"{network.ip.pool.gateway}"

            vm_data[f"net{network.net_id}"] = ",".join([f"{key}={value}" for key, value in net_data.items()])

        # Set DNS from the first network's pool
        first_network = service.service_network.first()
        if first_network and first_network.ip.pool.dns:
            vm_data["nameserver"] = first_network.ip.pool.dns

        if not service.bw_renewal_dtm:
            service.bw_renewal_dtm = timezone.now() + relativedelta(months=1)
            service.save()

        machine = None
        if service_type == "kvm":
            node.qemu(service.machine_id).config.post(**vm_data)
            lock = True
            poll_start = time.monotonic()
            while lock:
                if time.monotonic() - poll_start > MAX_POLL_SECONDS:
                    raise TimeoutError(f"Config lock poll timed out after {MAX_POLL_SECONDS}s for service {service_id}")
                status = node.qemu(service.machine_id).status.current.get()
                if "lock" not in status:
                    lock = False
                else:
                    time.sleep(1)
            node.qemu(service.machine_id).resize.put(disk="scsi0", size=f"{service.service_plan.size}G")
            machine = node.qemu(service.machine_id)
        if service_type == "lxc":
            try:
                node.lxc.create(vmid=service.machine_id, **vm_data)
            except ResourceException as e:
                if "already exists" in str(e):
                    # Existing container -- update config (skip create-only keys)
                    update_data = {
                        k: v
                        for k, v in vm_data.items()
                        if k not in ("ostemplate", "rootfs", "password", "unprivileged", "storage", "pool", "start")
                    }
                    node.lxc(service.machine_id).config.put(**update_data)
                else:
                    raise
            machine = node.lxc(service.machine_id)

        for network in service.service_network.all():
            try:
                cidrs = machine.firewall.ipset(f"ipfilter-net{network.net_id}").get()
                for cidr in cidrs:
                    machine.firewall.ipset(f"ipfilter-net{network.net_id}/{cidr['cidr']}").delete()
                machine.firewall.ipset(f"ipfilter-net{network.net_id}").delete()
            except ResourceException as e:
                if "no such IPSet" in str(e):
                    pass
                else:
                    raise
            machine.firewall.ipset.post(name=f"ipfilter-net{network.net_id}")
            machine.firewall.ipset(f"ipfilter-net{network.net_id}").post(cidr=f"{network.ip.value}")
        machine.firewall.options.put(enable=1, ipfilter=1)
        for rule in machine.firewall.rules.get():
            if rule["type"] == "group" and rule["action"] == "inveterate":
                break
        else:
            machine.firewall.rules.post(type="group", action="inveterate", enable=1)

        try:
            proxmox.pools("inveterate").put(vms=service.machine_id)
        except ResourceException as e:
            if "already a pool member" in str(e):
                pass
            else:
                raise
        logger.info(f"Successfully provisioned service {service_id} with machine_id {service.machine_id}")
    except NodeDisk.DoesNotExist:
        error_msg = f"No primary storage disk configured for node {service.node.name}"
        logger.error(f"Failed to provision service {service_id}: {error_msg}")
        Service.objects.filter(pk=service_id).update(status="error", status_msg=error_msg)
        raise
    except ConnectionError as e:
        error_msg = f"Cannot connect to Proxmox cluster at {service.node.cluster.host}"
        logger.error(f"Failed to provision service {service_id}: {error_msg} - {str(e)}")
        Service.objects.filter(pk=service_id).update(status="error", status_msg=error_msg)
        raise
    except ResourceException as e:
        error_msg = f"Proxmox API error: {str(e)}"
        logger.error(f"Failed to provision service {service_id}: {error_msg}")
        Service.objects.filter(pk=service_id).update(status="error", status_msg=error_msg)
        raise
    except Exception as e:
        error_msg = f"Unexpected error during provisioning: {str(e)}"
        logger.error(f"Failed to provision service {service_id}: {error_msg}", exc_info=True)
        Service.objects.filter(pk=service_id).update(status="error", status_msg=str(e))
        raise
    else:
        Service.objects.filter(pk=service_id).update(status="active", status_msg=None)
        logger.info(f"Service {service_id} status updated to active")

    # Import via the package so that tests can patch ``inveterate.tasks.calculate_inventory``
    import inveterate.tasks as _tasks

    _tasks.calculate_inventory.delay()
