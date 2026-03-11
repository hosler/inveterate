import time

import yaml
from celery import shared_task
from celery_singleton import Singleton
from dateutil.relativedelta import relativedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from ..models import IP, IPPool, NodeDisk, PortBlock, PortGateway, Service, ServiceNetwork
from ..provisioning_steps import progress_msg
from ..proxmox import get_proxmox_connection
from ._common import MAX_POLL_SECONDS, delete_snippet, logger, write_snippet


def _release_service_networking(service_id):
    """Release IPs and port blocks allocated during a failed provisioning attempt.

    This avoids tying up pool resources while a service sits in error state.
    Does NOT touch the Proxmox VM — admins can inspect and clean up manually.
    """
    networks = ServiceNetwork.objects.filter(service_id=service_id)
    released_ips = IP.objects.filter(owner__in=networks).update(owner=None)
    deleted_blocks = PortBlock.objects.filter(service_network__in=networks).delete()[0]
    deleted_networks = networks.delete()[0]
    if released_ips or deleted_blocks or deleted_networks:
        logger.info(
            "Released resources for failed service %s: %d IPs, %d port blocks, %d networks",
            service_id, released_ips, deleted_blocks, deleted_networks,
        )

_SSH_KEY_PREFIXES = (
    "ssh-rsa ",
    "ssh-ed25519 ",
    "ssh-dss ",
    "ecdsa-sha2-",
    "sk-ssh-ed25519@openssh.com ",
    "sk-ecdsa-sha2-",
)


def _wait_for_task(node, upid, service_id, label=""):
    """Poll a Proxmox task UPID until it completes."""
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


def _wait_for_unlock(node, machine_id, service_id, label=""):
    """Poll until the VM config is no longer locked."""
    poll_start = time.monotonic()
    while True:
        if time.monotonic() - poll_start > MAX_POLL_SECONDS:
            raise TimeoutError(f"Lock wait ({label}) timed out after {MAX_POLL_SECONDS}s for service {service_id}")
        status = node.qemu(machine_id).status.current.get()
        if "lock" not in status:
            return
        time.sleep(2)


def _compose_cloud_init(apps, ssh_keys=None, user=None, hostname=None, password=None, kvm=False):
    """Merge AppProfile cloud_init fragments into a single cloud-config document.

    When ``cicustom user=...`` is set on a Proxmox VM, it completely replaces
    the auto-generated user-data.  We therefore need to include ``user``,
    ``hostname``, ``manage_etc_hosts``, and ``fqdn`` ourselves so that
    cloud-init applies SSH keys and other settings to the correct account.

    Args:
        apps: QuerySet of AppProfile objects to merge.
        ssh_keys: Optional list of SSH public key strings to inject via cloud-init.
        user: Unix username that cloud-init should configure (maps to Proxmox ``ciuser``).
        hostname: VM hostname (written as ``hostname`` + ``fqdn`` in cloud-config).
        password: Hashed password string for ``chpasswd`` (Proxmox ``cipassword``).
        kvm: If True, include ``qemu-guest-agent`` package and enable the service.
    """
    merged_keys = ("packages", "runcmd", "write_files")
    merged = {}

    # Include identity fields that Proxmox would auto-generate but are lost
    # when ``cicustom`` overrides the user-data section.
    if user:
        merged["user"] = user
        merged["users"] = ["default"]
    if hostname:
        merged["hostname"] = hostname
        merged["manage_etc_hosts"] = True
        merged["fqdn"] = hostname
    if password:
        merged["password"] = password
        merged["chpasswd"] = {"expire": False}

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
    if kvm:
        merged.setdefault("packages", []).append("qemu-guest-agent")
        merged.setdefault("runcmd", []).append("systemctl enable --now qemu-guest-agent")
    if not merged:
        return ""
    return "#cloud-config\n" + yaml.dump(merged, default_flow_style=False)


@shared_task(name="inveterate.tasks.assign_ips", base=Singleton, lock_expiry=60 * 15)
def assign_ips(service_id):
    logger.info("Assigning IPs for service %s", service_id)
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
                raise RuntimeError(
                    f"No internal IP pools configured for node {service.node} (service {service_id})"
                )
        for i in range(ipv4_ips):
            if not _allocate_ip(lambda p: p.type == "ipv4" and p.internal is not True, "IPv4"):
                raise RuntimeError(
                    f"No IPv4 IP pools configured for node {service.node} (service {service_id})"
                )
        for i in range(ipv6_ips):
            if not _allocate_ip(lambda p: p.type == "ipv6" and p.internal is not True, "IPv6"):
                raise RuntimeError(
                    f"No IPv6 IP pools configured for node {service.node} (service {service_id})"
                )

    # Allocate port blocks for internal IPs that don't have one yet
    internal_networks = (
        ServiceNetwork.objects.filter(service=service, ip__pool__internal=True)
        .select_related("ip__pool")
        .exclude(port_block__isnull=False)
    )

    for sn in internal_networks:
        gateways = PortGateway.objects.filter(pools=sn.ip.pool)
        for gw in gateways:
            allocated = False
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        # Lock gateway's port blocks to find next available slot
                        existing_starts = set(
                            PortBlock.objects.select_for_update().filter(gateway=gw).values_list(
                                "port_start", flat=True
                            )
                        )
                        port = gw.port_range_start
                        while port + gw.block_size - 1 <= gw.port_range_end:
                            if port not in existing_starts:
                                PortBlock.objects.create(
                                    gateway=gw,
                                    service_network=sn,
                                    port_start=port,
                                    port_end=port + gw.block_size - 1,
                                )
                                logger.info(
                                    f"Allocated port block {port}-{port + gw.block_size - 1} "
                                    f"on {gw.name} for service {service_id}"
                                )
                                allocated = True
                                break
                            port += gw.block_size
                    if allocated:
                        break
                except IntegrityError:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Port block allocation conflict on {gw.name} (attempt {attempt + 1}), retrying"
                        )
                    else:
                        raise
            if not allocated:
                raise RuntimeError(
                    f"No available port block on gateway {gw.name} for service {service_id}"
                )


def _update_progress(service_id, step_key):
    """Write a provisioning progress marker to status_msg (single SQL UPDATE)."""
    Service.objects.filter(pk=service_id).update(status_msg=progress_msg(step_key))


def _provision_kvm(service, node, proxmox, password, ssh_keys):
    """Clone template, move disks, configure cloud-init for a KVM service."""
    service_id = service.id

    _update_progress(service_id, "clone_vm")
    # Find which node has the template
    clone_node = node
    template_vmid = int(service.service_plan.template.file)
    for resource in proxmox.cluster.resources.get(type="vm"):
        if resource["vmid"] == template_vmid:
            clone_node = proxmox.nodes(resource["node"])
            break

    target_storage = service.service_plan.storage.name
    cross_node = clone_node is not node

    # Cross-node clone requires shared storage as intermediate;
    # we move the disk to target storage afterwards.
    clone_storage = target_storage
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
    # Skip clone if VM already exists on the target node
    vm_exists = False
    try:
        node.qemu(service.machine_id).status.current.get()
        vm_exists = True
    except ResourceException:
        pass

    if not vm_exists:
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
            found_on_any_node = False
            for check_node in (node, clone_node):
                try:
                    status = check_node.qemu(service.machine_id).status.current.get()
                    found_on_any_node = True
                    if "lock" in status:
                        break  # Still locked, keep polling
                except ResourceException:
                    continue
            else:
                # Loop completed without finding a lock on any reachable node
                if found_on_any_node:
                    locked = False
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

    # Move disks from shared intermediate to target local storage
    if clone_storage != target_storage:
        _update_progress(service_id, "move_disks")
        config = node.qemu(service.machine_id).config.get()
        disks_to_move = [key for key, value in config.items() if isinstance(value, str) and f"{clone_storage}:" in value]

        for disk in disks_to_move:
            _wait_for_unlock(node, service.machine_id, service_id, "pre-move")
            logger.info("Moving %s from %s to %s for service %s", disk, clone_storage, target_storage, service_id)
            upid = node.qemu(service.machine_id).move_disk.post(disk=disk, storage=target_storage, delete=1)
            _wait_for_task(node, upid, service_id, f"move-{disk}")

    _update_progress(service_id, "cloud_init")
    vm_data = {
        "onboot": 1,
        "memory": service.service_plan.ram,
        "vcpus": service.service_plan.cores,
        "cores": service.service_plan.cores,
        "balloon": 0,
        "name": service.hostname,
        "ciuser": service.username or service.owner.email.split("@")[0],
        "agent": "1",
    }
    if password is not None:
        vm_data["cipassword"] = password

    ci_content = _compose_cloud_init(
        service.service_plan.apps.all(),
        ssh_keys=ssh_keys,
        user=vm_data.get("ciuser"),
        hostname=service.hostname,
        password=password,
        kvm=True,
    )
    if ci_content:
        snippet_name = f"ci-{service.machine_id}.yml"
        write_snippet(proxmox, service.node.name, snippet_name, ci_content)
        vm_data["cicustom"] = f"user=local:snippets/{snippet_name}"

    return vm_data


def _build_lxc_config(service, password):
    """Build the LXC container configuration dict."""
    return {
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


def _build_network_config(service, service_type, vm_data):
    """Add network interfaces and DNS to vm_data from assigned IPs."""
    for network in service.service_network.all():
        firewall = 1 if network.ip.pool.internal is True else 0
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

    first_network = service.service_network.first()
    if first_network and first_network.ip.pool.dns:
        vm_data["nameserver"] = first_network.ip.pool.dns


def _create_or_update_lxc(node, service, vm_data):
    """Create an LXC container, or update its config if it already exists."""
    try:
        node.lxc.create(vmid=service.machine_id, **vm_data)
    except ResourceException as e:
        if "already exists" in str(e):
            update_data = {
                k: v
                for k, v in vm_data.items()
                if k not in ("ostemplate", "rootfs", "password", "unprivileged", "storage", "pool", "start")
            }
            node.lxc(service.machine_id).config.put(**update_data)
        else:
            raise
    return node.lxc(service.machine_id)


def _apply_kvm_config(node, service, vm_data):
    """Apply KVM config, wait for lock, resize disk."""
    service_id = service.id
    node.qemu(service.machine_id).config.post(**vm_data)
    poll_start = time.monotonic()
    while True:
        if time.monotonic() - poll_start > MAX_POLL_SECONDS:
            raise TimeoutError(f"Config lock poll timed out after {MAX_POLL_SECONDS}s for service {service_id}")
        status = node.qemu(service.machine_id).status.current.get()
        if "lock" not in status:
            break
        time.sleep(1)
    node.qemu(service.machine_id).resize.put(disk="scsi0", size=f"{service.service_plan.size}G")
    return node.qemu(service.machine_id)


def _setup_firewall(machine, service):
    """Configure IP filters and firewall rules on the VM."""
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


def _cleanup_snippet_on_failure(proxmox, service):
    """Best-effort cleanup of cloud-init snippet after a failed provisioning attempt."""
    if service.machine_id:
        try:
            snippet_name = f"ci-{service.machine_id}.yml"
            delete_snippet(proxmox, service.node.name, snippet_name)
        except Exception:
            logger.warning("Failed to clean up snippet for service %s", service.id)


@shared_task(
    name="inveterate.tasks.provision_service",
    base=Singleton,
    lock_expiry=60 * 15,
    autoretry_for=(ConnectionError,),
    retry_backoff=10,
    retry_backoff_max=120,
    max_retries=3,
)
def provision_service(service_id, password, ssh_keys=None):
    logger.info("Starting provisioning for service %s", service_id)
    service = Service.objects.get(pk=service_id)

    # Idempotency guard: skip if destroyed
    if service.status == "destroyed":
        logger.warning("Service %s is destroyed, skipping provisioning", service_id)
        return

    logger.info("Provisioning %s service '%s' on node %s", service.service_plan.type, service.hostname, service.node.name)

    proxmox = get_proxmox_connection(service.node.cluster, timeout=600)
    node = proxmox.nodes(service.node)
    service_type = service.service_plan.type
    try:
        proxmox.pools.post(poolid="inveterate")
    except ResourceException:
        pass

    if not service.service_plan.storage:
        service.service_plan.storage = NodeDisk.objects.get(node=service.node, primary=True)

    # Generate machine_id, avoiding collisions
    if not service.machine_id:
        with transaction.atomic():
            locked_svc = Service.objects.select_for_update().get(pk=service_id)
            if not locked_svc.machine_id:
                candidate = int(f"1{locked_svc.id:06}")
                existing_vmids = {r["vmid"] for r in proxmox.cluster.resources.get(type="vm")}
                existing_vmids.update(Service.objects.exclude(machine_id=None).values_list("machine_id", flat=True))
                max_vmid = 999999999  # Proxmox VMID upper limit
                while candidate in existing_vmids:
                    candidate += 1
                    if candidate > max_vmid:
                        raise RuntimeError("VMID allocation exhausted — no available IDs below %d" % max_vmid)
                locked_svc.machine_id = candidate
                locked_svc.save(update_fields=["machine_id"])
            service.machine_id = locked_svc.machine_id

    try:
        _update_progress(service_id, "assign_ips")
        assign_ips(service_id)

        if service_type == "kvm":
            vm_data = _provision_kvm(service, node, proxmox, password, ssh_keys)
        else:
            _update_progress(service_id, "configure")
            vm_data = _build_lxc_config(service, password)

        _update_progress(service_id, "network")
        _build_network_config(service, service_type, vm_data)

        if not service.bw_renewal_dtm:
            service.bw_renewal_dtm = timezone.now() + relativedelta(months=1)
            service.save()

        _update_progress(service_id, "configure")
        if service_type == "kvm":
            machine = _apply_kvm_config(node, service, vm_data)
        else:
            machine = _create_or_update_lxc(node, service, vm_data)

        _update_progress(service_id, "firewall")
        _setup_firewall(machine, service)

        _update_progress(service_id, "finalize")
        try:
            proxmox.pools("inveterate").put(vms=service.machine_id)
        except ResourceException as e:
            if "already a pool member" not in str(e):
                raise
        logger.info("Successfully provisioned service %s with machine_id %s", service_id, service.machine_id)
    except NodeDisk.DoesNotExist:
        error_msg = f"No primary storage disk configured for node {service.node.name}"
        logger.error("Failed to provision service %s: %s", service_id, error_msg)
        Service.objects.filter(pk=service_id).update(status="error", status_msg=error_msg)
        _release_service_networking(service_id)
        _cleanup_snippet_on_failure(proxmox, service)
        raise
    except ConnectionError as e:
        error_msg = f"Cannot connect to Proxmox cluster at {service.node.cluster.host}"
        logger.error("Failed to provision service %s: %s - %s", service_id, error_msg, e)
        Service.objects.filter(pk=service_id).update(status="error", status_msg=error_msg)
        _release_service_networking(service_id)
        _cleanup_snippet_on_failure(proxmox, service)
        raise
    except ResourceException as e:
        error_msg = f"Proxmox API error: {str(e)}"
        logger.error("Failed to provision service %s: %s", service_id, error_msg)
        Service.objects.filter(pk=service_id).update(status="error", status_msg=error_msg)
        _release_service_networking(service_id)
        _cleanup_snippet_on_failure(proxmox, service)
        raise
    except Exception as e:
        error_msg = f"Unexpected error during provisioning: {str(e)}"
        logger.error("Failed to provision service %s: %s", service_id, error_msg, exc_info=True)
        Service.objects.filter(pk=service_id).update(status="error", status_msg=str(e))
        _release_service_networking(service_id)
        _cleanup_snippet_on_failure(proxmox, service)
        raise
    else:
        Service.objects.filter(pk=service_id).update(status="active", status_msg=None)
        logger.info("Service %s status updated to active", service_id)

    # Import via the package so that tests can patch ``inveterate.tasks.calculate_inventory``
    import inveterate.tasks as _tasks

    _tasks.calculate_inventory.delay()
