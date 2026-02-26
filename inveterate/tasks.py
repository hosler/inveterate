import logging
import re
import time
from io import BytesIO

import yaml
from django.conf import settings
from celery import shared_task
from celery_singleton import Singleton
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from .models import (
    Node, Plan, Inventory, Service, Cluster, IP, ServiceNetwork, IPPool,
    NodeDisk, Template, PortGateway, PortBlock, PortForward, DomainRoute,
)

logger = logging.getLogger(__name__)


@shared_task(base=Singleton, lock_expiry=60 * 15)
def calculate_inventory():
    logger.info("Starting inventory calculation")
    plans = Plan.objects.all()
    nodes = Node.objects.all()
    inventory_fields = ['cores', 'ram']

    for node in nodes:
        services = node.services.all().exclude(status='destroyed')
        for plan in plans:
            lowest = None
            for field in inventory_fields:
                services_value = list(services.aggregate(Sum("service_plan__" + field)).values())[0]
                if services_value is None:
                    services_value = 0
                node_value = getattr(node, field)
                plan_value = getattr(plan, field)
                try:
                    quantity = int((node_value - services_value) / plan_value)
                except ZeroDivisionError:
                    quantity = float('inf')
                if lowest is None:
                    lowest = quantity
                elif quantity < lowest:
                    lowest = quantity

            # Disk accounting: use primary disk, fall back to largest
            primary_disk = node.node_disk.filter(primary=True).first()
            if not primary_disk:
                primary_disk = node.node_disk.order_by('-size').first()
            if primary_disk and plan.size > 0:
                if primary_disk.shared:
                    # Sum usage across all nodes sharing this storage name
                    disk_used = Service.objects.filter(
                        service_plan__storage__name=primary_disk.name,
                        service_plan__storage__shared=True
                    ).exclude(status='destroyed').aggregate(
                        total=Sum('service_plan__size')
                    )['total'] or 0
                else:
                    disk_used = services.aggregate(
                        total=Sum('service_plan__size')
                    )['total'] or 0
                disk_slots = int((primary_disk.size - disk_used) / plan.size)
                if lowest is None or disk_slots < lowest:
                    lowest = disk_slots

            # IP accounting: check available IPs in pools assigned to this node
            node_pools = IPPool.objects.filter(nodes=node)
            for ip_type, plan_field in [('internal', 'internal_ips'), ('ipv4', 'ipv4_ips'), ('ipv6', 'ipv6_ips')]:
                needed = getattr(plan, plan_field)
                if needed <= 0:
                    continue
                if ip_type == 'internal':
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
            logger.debug(f"Node {node.name}, Plan {plan.name}: {inventory.quantity} slots available")

    # Cluster-level bandwidth cap
    for cluster in Cluster.objects.all():
        if cluster.bandwidth <= 0:
            continue
        cluster_nodes = nodes.filter(cluster=cluster)
        bw_used = Service.objects.filter(
            node__cluster=cluster
        ).exclude(status='destroyed').aggregate(
            total=Sum('service_plan__bandwidth')
        )['total'] or 0
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
                        logger.debug(
                            f"Node {node.name}, Plan {plan.name}: capped to {bw_slots} by cluster bandwidth"
                        )
                except Inventory.DoesNotExist:
                    pass

    logger.info("Inventory calculation completed")


@shared_task(base=Singleton, lock_expiry=60 * 15)
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
    for i in range(internal_ips):
        for pool in ip_pools:
            if pool.internal is False:
                continue
            with transaction.atomic():
                ip = IP.objects.select_for_update(skip_locked=True).filter(owner=None, pool=pool).first()
                if ip:
                    service_network = ServiceNetwork.objects.create(service=service)
                    ip.owner = service_network
                    ip.save()
                    break
    for i in range(ipv4_ips):
        for pool in ip_pools:
            if pool.type != "ipv4" or pool.internal is True:
                continue
            with transaction.atomic():
                ip = IP.objects.select_for_update(skip_locked=True).filter(owner=None, pool=pool).first()
                if ip:
                    service_network = ServiceNetwork.objects.create(service=service)
                    ip.owner = service_network
                    ip.save()
                    break
    for i in range(ipv6_ips):
        for pool in ip_pools:
            if pool.type != "ipv6" or pool.internal is True:
                continue
            with transaction.atomic():
                ip = IP.objects.select_for_update(skip_locked=True).filter(owner=None, pool=pool).first()
                if ip:
                    service_network = ServiceNetwork.objects.create(service=service)
                    ip.owner = service_network
                    ip.save()
                    break

    # Allocate port blocks for internal IPs that don't have one yet
    internal_networks = ServiceNetwork.objects.filter(
        service=service, ip__pool__internal=True
    ).select_related('ip__pool').exclude(port_block__isnull=False)

    for sn in internal_networks:
        gateways = PortGateway.objects.filter(pools=sn.ip.pool)
        for gw in gateways:
            with transaction.atomic():
                # Lock gateway's port blocks to find next available slot
                existing_starts = set(
                    PortBlock.objects.select_for_update()
                    .filter(gateway=gw)
                    .values_list('port_start', flat=True)
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
                        logger.info(f"Allocated port block {port}-{port + gw.block_size - 1} on {gw.name} for service {service_id}")
                        allocated = True
                        break
                    port += gw.block_size
                if not allocated:
                    logger.warning(f"No available port block on gateway {gw.name} for service {service_id}")


def _compose_cloud_init(apps):
    """Merge AppProfile cloud_init fragments into a single cloud-config document."""
    merged_keys = ('packages', 'runcmd', 'write_files')
    merged = {}
    for app in apps.order_by('pk'):
        fragment = yaml.safe_load(app.cloud_init)
        if not isinstance(fragment, dict):
            continue
        for key in merged_keys:
            if key in fragment:
                merged.setdefault(key, []).extend(fragment[key])
    if not merged:
        return ''
    return '#cloud-config\n' + yaml.dump(merged, default_flow_style=False)


@shared_task(base=Singleton, lock_expiry=60 * 15)
def provision_service(service_id, password):
    logger.info(f"Starting provisioning for service {service_id}")
    service = Service.objects.get(pk=service_id)
    logger.info(f"Provisioning {service.service_plan.type} service '{service.hostname}' on node {service.node.name}")

    proxmox = ProxmoxAPI(service.node.cluster.host, user=service.node.cluster.user, token_name='inveterate',
                         token_value=service.node.cluster.key,
                         verify_ssl=False, port=8006, timeout=600)
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
        candidate = int(f"1{service.id:06}")
        existing_vmids = {
            r['vmid']
            for r in proxmox.cluster.resources.get(type='vm')
        }
        existing_vmids.update(
            Service.objects.exclude(machine_id=None)
            .values_list('machine_id', flat=True)
        )
        while candidate in existing_vmids:
            candidate += 1
        service.machine_id = candidate
        service.save(update_fields=['machine_id'])
    try:
        logger.debug(f"Assigning IPs for service {service_id}")
        assign_ips(service_id)
        logger.debug(f"IP assignment completed for service {service_id}")

        if service_type == "kvm":
            # Find which node has the template
            clone_node = node
            template_vmid = int(service.service_plan.template.file)
            for resource in proxmox.cluster.resources.get(type='vm'):
                if resource['vmid'] == template_vmid:
                    clone_node = proxmox.nodes(resource['node'])
                    break

            # Cross-node clone requires shared storage; use it as
            # intermediate then move to the target disk if needed.
            target_storage = service.service_plan.storage.name
            clone_storage = target_storage
            cross_node = (clone_node is not node)
            if cross_node:
                shared_disk = NodeDisk.objects.filter(
                    node=service.node, shared=True
                ).first()
                if shared_disk:
                    clone_storage = shared_disk.name

            clone_data = {
                'newid': service.machine_id,
                'storage': clone_storage,
                'full': 1,
                'target': service.node.name,
            }
            try:
                clone_node.qemu(service.service_plan.template.file).clone.post(**clone_data)
                # Wait for clone to finish (check both source and target
                # nodes since the VM may briefly live on the source).
                locked = True
                while locked:
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
                    while True:
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
                'onboot': 1,
                'memory': service.service_plan.ram,
                'vcpus': service.service_plan.cores,
                'cores': service.service_plan.cores,
                'balloon': 0,
                'name': service.hostname,
                'ciuser': service.owner,
            }
            if password is not None:
                vm_data['cipassword'] = password

            # Compose and upload cloud-init snippet for selected app profiles
            if service.service_plan.apps.exists():
                ci_content = _compose_cloud_init(service.service_plan.apps.all())
                if ci_content:
                    snippet_name = f'ci-{service.machine_id}.yml'
                    node.storage('local').upload.post(
                        content='snippets',
                        filename=snippet_name,
                        file=BytesIO(ci_content.encode()),
                    )
                    vm_data['cicustom'] = f'user=local:snippets/{snippet_name}'

        if service_type == "lxc":
            vm_data = {
                'ostemplate': f'local:vztmpl/{service.service_plan.template.file}',
                'hostname': service.hostname,
                'storage': service.service_plan.storage.name,
                'memory': service.service_plan.ram,
                'swap': service.service_plan.swap,
                'cores': service.service_plan.cores,
                'rootfs': f'{service.service_plan.storage.name}:{service.service_plan.size}',
                'password': password,
                'unprivileged': '1',
                'onboot': '1',
                'start': '1',
                'searchdomain': service.hostname,
                'pool': 'inveterate'
            }

        # Build network configuration from assigned IPs
        for network in service.service_network.all():
            firewall = 0
            if network.ip.pool.internal is True:
                firewall = 1
            net_data = {
                'bridge': network.ip.pool.interface,
                'firewall': firewall,
            }
            if network.ip.pool.vlan_tag:
                net_data['tag'] = network.ip.pool.vlan_tag
            if service_type == "kvm":
                net_data['model'] = 'virtio'
                if network.ip.pool.type == "ipv4":
                    vm_data[f'ipconfig{network.net_id}'] = f'ip={network.ip.value}/{network.ip.pool.mask},' \
                                                           f'gw={network.ip.pool.gateway}'
                else:
                    vm_data[f'ipconfig{network.net_id}'] = f'ip6={network.ip.value}/{network.ip.pool.mask},' \
                                                           f'gw6={network.ip.pool.gateway}'
            if service_type == "lxc":
                net_data['name'] = f'eth{network.net_id}'
                if network.ip.pool.type == "ipv4":
                    net_data['ip'] = f'{network.ip.value}/{network.ip.pool.mask}'
                    net_data['gw'] = f'{network.ip.pool.gateway}'
                else:
                    net_data['ip6'] = f'{network.ip.value}/{network.ip.pool.mask}'
                    net_data['gw6'] = f'{network.ip.pool.gateway}'

            vm_data[f'net{network.net_id}'] = ",".join([f'{key}={value}' for key, value in net_data.items()])

        # Set DNS from the first network's pool
        first_network = service.service_network.first()
        if first_network and first_network.ip.pool.dns:
            vm_data['nameserver'] = first_network.ip.pool.dns

        if not service.bw_renewal_dtm:
            service.bw_renewal_dtm = timezone.now() + relativedelta(months=1)
            service.save()

        machine = None
        if service_type == "kvm":
            node.qemu(service.machine_id).config.post(**vm_data)
            lock = True
            while lock:
                status = node.qemu(service.machine_id).status.current.get()
                if "lock" not in status:
                    lock = False
                else:
                    time.sleep(1)
            node.qemu(service.machine_id).resize.put(disk='scsi0', size=f'{service.service_plan.size}G')
            machine = node.qemu(service.machine_id)
        if service_type == "lxc":
            try:
                node.lxc.create(vmid=service.machine_id, **vm_data)
            except ResourceException as e:
                if "already exists" in str(e):
                    # Existing container — update config (skip create-only keys)
                    update_data = {k: v for k, v in vm_data.items()
                                   if k not in ('ostemplate', 'rootfs', 'password',
                                                'unprivileged', 'storage', 'pool', 'start')}
                    node.lxc(service.machine_id).config.put(**update_data)
                else:
                    raise
            machine = node.lxc(service.machine_id)

        for network in service.service_network.all():
            try:
                cidrs = machine.firewall.ipset(f'ipfilter-net{network.net_id}').get()
                for cidr in cidrs:
                    machine.firewall.ipset(f"ipfilter-net{network.net_id}/{cidr['cidr']}").delete()
                machine.firewall.ipset(f'ipfilter-net{network.net_id}').delete()
            except ResourceException as e:
                if "no such IPSet" in str(e):
                    pass
                else:
                    raise
            machine.firewall.ipset.post(name=f'ipfilter-net{network.net_id}')
            machine.firewall.ipset(f'ipfilter-net{network.net_id}').post(cidr=f'{network.ip.value}')
        machine.firewall.options.put(enable=1, ipfilter=1)
        for rule in machine.firewall.rules.get():
            if rule['type'] == 'group' and rule['action'] == 'inveterate':
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
        service.status = "error"
        service.status_msg = error_msg
        service.save()
        raise
    except ConnectionError as e:
        error_msg = f"Cannot connect to Proxmox cluster at {service.node.cluster.host}"
        logger.error(f"Failed to provision service {service_id}: {error_msg} - {str(e)}")
        service.status = "error"
        service.status_msg = error_msg
        service.save()
        raise
    except ResourceException as e:
        error_msg = f"Proxmox API error: {str(e)}"
        logger.error(f"Failed to provision service {service_id}: {error_msg}")
        service.status = "error"
        service.status_msg = error_msg
        service.save()
        raise
    except Exception as e:
        error_msg = f"Unexpected error during provisioning: {str(e)}"
        logger.error(f"Failed to provision service {service_id}: {error_msg}", exc_info=True)
        service.status = "error"
        service.status_msg = str(e)
        service.save()
        raise
    else:
        service.status = "active"
        service.status_msg = None
        service.save()
        logger.info(f"Service {service_id} status updated to {service.status}")

    calculate_inventory.delay()


def get_vm(service_id):
    from .proxmox import get_proxmox_connection
    service = Service.objects.get(pk=service_id)
    proxmox = get_proxmox_connection(service.node.cluster)
    node = proxmox.nodes(service.node)
    machine = None
    if service.service_plan.type == "kvm":
        machine = node.qemu(service.machine_id)
    if service.service_plan.type == "lxc":
        machine = node.lxc(service.machine_id)
    return machine, service


def get_service_node(service_id):
    from .proxmox import get_proxmox_connection
    service = Service.objects.get(pk=service_id)
    proxmox = get_proxmox_connection(service.node.cluster)
    node = proxmox.nodes(service.node)
    return node


def get_cluster(cluster_id):
    from .proxmox import get_proxmox_connection
    cluster = Cluster.objects.get(pk=cluster_id)
    proxmox = get_proxmox_connection(cluster)
    return proxmox.cluster


@shared_task(base=Singleton, lock_expiry=60 * 15)
def start_vm(service_id):
    logger.info(f"Starting VM for service {service_id}")
    machine, service = get_vm(service_id)
    machine.status.start.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def stop_vm(service_id):
    logger.info(f"Stopping VM for service {service_id}")
    machine, service = get_vm(service_id)
    machine.status.stop.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def reset_vm(service_id):
    logger.info(f"Resetting VM for service {service_id}")
    machine, service = get_vm(service_id)
    machine.status.reset.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def shutdown_vm(service_id):
    logger.info(f"Shutting down VM for service {service_id}")
    machine, service = get_vm(service_id)
    machine.status.shutdown.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def reboot_vm(service_id):
    logger.info(f"Rebooting VM for service {service_id}")
    machine, service = get_vm(service_id)
    machine.status.reboot.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def get_vm_status(service_id):
    machine, service = get_vm(service_id)
    vm_stats = machine.status.current.get()
    stats = {
        "status": vm_stats['status'],
        "mem_max": vm_stats['maxmem'],
        "mem_used": vm_stats['mem'],
        "disk_max": vm_stats['maxdisk'],
        "disk_used": vm_stats['diskwrite'],
        "cpu_util": vm_stats['cpu'],
        #"bandwidth_max": service.service_plan.bandwidth * 1024 * 1024,
        #"bandwidth_used": service.bw_usage + service.bw_banked
    }
    return stats


def get_vm_ips(service_id):
    networks = ServiceNetwork.objects.filter(service_id=service_id).select_related('ip__pool')
    ips = []
    for network in networks:
        ip = {
            "value": network.ip.value,
            "primary": network.net_id == 0,
        }
        if network.ip.pool.internal and hasattr(network, 'port_block'):
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


@shared_task(base=Singleton, lock_expiry=60 * 15)
def get_cluster_resources(pk=None, query_type="node"):
    cluster = get_cluster(cluster_id=pk)
    if query_type == "vm":
        stats = []
        vms = cluster.resources.get(type=query_type)
        for vm in vms:
            if 'pool' in vm and vm['pool'] == 'inveterate':
                stats.append(vm)
    elif query_type == 'storage':
        stats = []
        disks = cluster.resources.get(type=query_type)
        for disk in disks:
            content = disk['content'].split(",")
            if "rootdir" in content:
                stats.append(disk)
    else:
        stats = cluster.resources.get(type=query_type)
    return stats


@shared_task(base=Singleton, lock_expiry=60 * 15)
def suspend_service(service_id):
    machine, service = get_vm(service_id)
    machine.status.suspend.post(todisk=1)
    service.status = "suspended"
    service.save()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def reinstate_service(service_id):
    machine, service = get_vm(service_id)
    machine.status.start.post()
    service.status = "active"
    service.save()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def cancel_service(service_id):
    machine, service = get_vm(service_id)
    machine.delete(force=1)

    # Clean up cloud-init snippet if one was uploaded
    if service.service_plan and service.service_plan.type == 'kvm' and service.machine_id:
        try:
            node = get_service_node(service_id)
            node.storage('local').content.delete(f'snippets/ci-{service.machine_id}.yml')
        except Exception:
            pass

    # Clean up NPM resources (port forwards and domain routes)
    for sn in service.service_network.all():
        if hasattr(sn, 'port_block'):
            for pf in sn.port_block.forwards.filter(npm_stream_id__isnull=False):
                try:
                    from .npm import NPMClient
                    client = NPMClient(
                        sn.port_block.gateway.host,
                        sn.port_block.gateway.admin_email,
                        sn.port_block.gateway.admin_password,
                    )
                    client.delete_stream(pf.npm_stream_id)
                    logger.info(f"Deleted NPM stream {pf.npm_stream_id} for service {service_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete NPM stream {pf.npm_stream_id}: {e}")

    for dr in service.domain_routes.filter(npm_proxy_host_id__isnull=False):
        # Find the gateway via any internal service network
        internal_sn = service.service_network.filter(ip__pool__internal=True).first()
        if internal_sn and hasattr(internal_sn, 'port_block'):
            try:
                from .npm import NPMClient
                client = NPMClient(
                    internal_sn.port_block.gateway.host,
                    internal_sn.port_block.gateway.admin_email,
                    internal_sn.port_block.gateway.admin_password,
                )
                client.delete_proxy_host(dr.npm_proxy_host_id)
                logger.info(f"Deleted NPM proxy host {dr.npm_proxy_host_id} for service {service_id}")
            except Exception as e:
                logger.warning(f"Failed to delete NPM proxy host {dr.npm_proxy_host_id}: {e}")

    # Release IPs back to the pool by deleting ServiceNetwork records.
    # IP.owner is a OneToOneField with on_delete=SET_NULL, so deleting
    # the ServiceNetwork automatically sets IP.owner = NULL.
    service.service_network.all().delete()

    service.status = "destroyed"
    service.save()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def cleanup_orphaned_ips():
    """
    Safety-net task to release IPs orphaned by past bugs or edge cases.
    Finds ServiceNetwork records belonging to destroyed services and deletes
    them, which auto-nulls IP.owner via the SET_NULL cascade.
    """
    logger.info("Starting orphaned IP cleanup")
    orphaned = ServiceNetwork.objects.filter(service__status='destroyed')
    count = orphaned.count()
    if count:
        orphaned.delete()
        logger.info(f"Cleaned up {count} orphaned ServiceNetwork records")
    else:
        logger.info("No orphaned IPs found")


@shared_task(base=Singleton, lock_expiry=60 * 15)
def meter_bandwidth():
    logger.info("Starting bandwidth metering")
    api_objects = {}
    services_to_update = []
    now = timezone.now()

    # Optimize query with select_related to avoid N+1 queries
    services = Service.objects.filter(status="active").select_related(
        'node', 'node__cluster', 'service_plan'
    )

    services_processed = 0
    services_failed = 0

    for service in services:
        try:
            # Skip if no bandwidth tracking
            if not service.bw_renewal_dtm:
                logger.debug(f"Service {service.id} has no bandwidth tracking, skipping")
                continue

            node_name = service.node.name
            if node_name not in api_objects:
                api_objects[node_name] = ProxmoxAPI(
                    service.node.cluster.host,
                    user=service.node.cluster.user,
                    token_name='inveterate',
                    token_value=service.node.cluster.key,
                    verify_ssl=False,
                    port=8006
                )
            node = api_objects[node_name].nodes(node_name)

            # Handle bandwidth renewal
            if now > service.bw_renewal_dtm:
                service.bw_renewal_dtm = now + relativedelta(months=1)
                service.bw_stale += service.bw_usage
                service.bw_banked = 0
                logger.info(f"Renewed bandwidth for service {service.id}")

            # Get VM stats
            if service.service_plan.type == "lxc":
                machine = node.lxc(service.machine_id)
            elif service.service_plan.type == "kvm":
                machine = node.qemu(service.machine_id)
            else:
                logger.warning(f"Unknown service type {service.service_plan.type} for service {service.id}")
                continue

            data = machine.status.current.get()
            tick = data["uptime"]

            if tick > service.bw_system_tick:
                try:
                    service.bw_usage = data["netin"] + data["netout"]
                except KeyError as e:
                    logger.warning(f"Missing network data for service {service.id}: {e}")
            elif tick < service.bw_system_tick:
                # VM was restarted
                banked = service.bw_usage - service.bw_stale
                service.bw_banked += banked
                service.bw_usage = 0
                service.bw_stale = 0
                try:
                    service.bw_usage = data["netin"] + data["netout"]
                except KeyError as e:
                    logger.warning(f"Missing network data for service {service.id}: {e}")

            service.bw_system_tick = tick
            services_to_update.append(service)
            services_processed += 1

        except ResourceException as e:
            logger.error(f"Proxmox API error for service {service.id}: {str(e)}")
            services_failed += 1
        except Exception as e:
            logger.error(f"Failed to meter bandwidth for service {service.id}: {str(e)}", exc_info=True)
            services_failed += 1

    # Bulk update all service bandwidth records
    if services_to_update:
        Service.objects.bulk_update(
            services_to_update,
            ['bw_usage', 'bw_stale', 'bw_banked', 'bw_system_tick', 'bw_renewal_dtm']
        )
        logger.info(f"Bandwidth metering completed: {services_processed} services processed, {services_failed} failed, {len(services_to_update)} updated")
    else:
        logger.info("No bandwidth data to update")


@shared_task(base=Singleton, lock_expiry=60 * 15)
def cleanup_console_users():
    """
    Clean up orphaned Proxmox console users.

    Current format: ``inv-s{service_id}@pve`` (per-service).
    Also cleans up legacy ``inveterate{owner_id}@pve`` users left over from
    the previous per-owner naming scheme.
    """
    from .proxmox import get_proxmox_connection, is_console_user, is_legacy_console_user

    logger.info("Starting console user cleanup")

    active_service_ids = set(
        Service.objects.exclude(status='destroyed')
        .values_list('id', flat=True)
    )
    # Legacy fallback: owners who still have active services
    active_owner_ids = set(
        Service.objects.exclude(status='destroyed')
        .values_list('owner_id', flat=True)
        .distinct()
    )

    cleaned_up = 0
    errors = 0

    for cluster in Cluster.objects.all():
        try:
            proxmox = get_proxmox_connection(cluster)
            users = proxmox.access.users.get()

            for user in users:
                userid = user.get('userid', '')

                # Per-service users (current format)
                service_id = is_console_user(userid)
                if service_id is not None:
                    if service_id not in active_service_ids:
                        proxmox.access.users(userid).delete()
                        logger.info(f"Deleted orphaned console user: {userid}")
                        cleaned_up += 1
                    continue

                # Legacy per-owner users (transitional cleanup)
                owner_id = is_legacy_console_user(userid)
                if owner_id is not None:
                    if owner_id not in active_owner_ids:
                        proxmox.access.users(userid).delete()
                        logger.info(f"Deleted legacy console user: {userid}")
                        cleaned_up += 1

        except ConnectionError as e:
            logger.error(f"Cannot connect to cluster {cluster.name}: {str(e)}")
            errors += 1
        except ResourceException as e:
            logger.error(f"Proxmox API error on cluster {cluster.name}: {str(e)}")
            errors += 1
        except Exception as e:
            logger.error(f"Failed to cleanup console users on cluster {cluster.name}: {str(e)}", exc_info=True)
            errors += 1

    logger.info(f"Console user cleanup completed: {cleaned_up} users removed, {errors} clusters with errors")


@shared_task(base=Singleton, lock_expiry=60 * 15)
def sync_templates():
    """
    Ensure all registered LXC templates are downloaded to every node.
    KVM templates are VM-based (cloned, not downloaded) so they are skipped.
    """
    logger.info("Starting template sync")
    lxc_templates = Template.objects.filter(type='lxc')
    if not lxc_templates.exists():
        logger.info("No LXC templates registered — nothing to sync")
        return

    downloaded = 0
    already_present = 0
    errors = 0

    for cluster in Cluster.objects.all():
        try:
            proxmox = ProxmoxAPI(
                cluster.host,
                user=cluster.user,
                token_name='inveterate',
                token_value=cluster.key,
                verify_ssl=False,
                port=8006,
                timeout=120
            )

            for node in Node.objects.filter(cluster=cluster):
                # Get templates already on this node
                try:
                    existing = {
                        item['volid']
                        for item in proxmox.nodes(node.name).storage('local').content.get()
                        if item.get('content') == 'vztmpl'
                    }
                except ResourceException as e:
                    logger.error(f"Cannot list storage on {node.name}: {e}")
                    errors += 1
                    continue

                for template in lxc_templates:
                    volid = f"local:vztmpl/{template.file}"
                    if volid in existing:
                        already_present += 1
                        continue

                    # Check appliance index for this template
                    try:
                        available = proxmox.nodes(node.name).aplinfo.get()
                        match = next(
                            (t for t in available if t.get('template') == template.file),
                            None
                        )
                        if not match:
                            logger.warning(
                                f"Template '{template.file}' not found in appliance index for {node.name}"
                            )
                            errors += 1
                            continue

                        logger.info(f"Downloading '{template.file}' to {node.name}")
                        proxmox.nodes(node.name).aplinfo.post(
                            storage='local',
                            template=template.file
                        )
                        downloaded += 1
                    except ResourceException as e:
                        logger.error(f"Failed to download '{template.file}' to {node.name}: {e}")
                        errors += 1

        except ConnectionError as e:
            logger.error(f"Cannot connect to cluster {cluster.name}: {e}")
            errors += 1
        except Exception as e:
            logger.error(f"Error syncing templates on cluster {cluster.name}: {e}", exc_info=True)
            errors += 1

    logger.info(
        f"Template sync completed: {downloaded} downloaded, "
        f"{already_present} already present, {errors} errors"
    )


def _wait_for_proxmox_task(node, upid, timeout=600):
    """Poll a Proxmox task UPID until it stops. Raises on failure or timeout."""
    elapsed = 0
    while elapsed < timeout:
        task_status = node.tasks(upid).status.get()
        if task_status['status'] == 'stopped':
            if task_status.get('exitstatus', '') != 'OK':
                raise RuntimeError(
                    f"Proxmox task {upid} failed: {task_status.get('exitstatus', 'unknown')}"
                )
            return task_status
        time.sleep(5)
        elapsed += 5
    raise TimeoutError(f"Proxmox task {upid} timed out after {timeout}s")


@shared_task(base=Singleton, lock_expiry=60 * 30)
def import_kvm_template(template_id):
    """Download a cloud image and create a KVM template VM in Proxmox."""
    logger.info(f"Starting KVM template import for template {template_id}")
    template = Template.objects.get(pk=template_id)

    if template.type != 'kvm':
        template.status = 'error'
        template.status_msg = 'Only KVM templates can be imported'
        template.save()
        logger.error(f"Template {template_id} is not KVM type")
        return

    if not template.source_url:
        template.status = 'error'
        template.status_msg = 'source_url is required for cloud image import'
        template.save()
        logger.error(f"Template {template_id} has no source_url")
        return

    template.status = 'importing'
    template.status_msg = ''
    template.save()

    # Pick target node
    target_node = None
    if template.node:
        target_node = template.node
    else:
        target_node = Node.objects.first()
        if not target_node:
            template.status = 'error'
            template.status_msg = 'No nodes available'
            template.save()
            logger.error(f"No nodes available for template {template_id}")
            return
        template.node = target_node
        template.save(update_fields=['node'])

    cluster = target_node.cluster
    try:
        proxmox = ProxmoxAPI(
            cluster.host, user=cluster.user, token_name='inveterate',
            token_value=cluster.key, verify_ssl=False, port=8006, timeout=600,
        )
        node = proxmox.nodes(target_node.name)

        # Get primary storage for VM disk
        primary_disk = NodeDisk.objects.get(node=target_node, primary=True)
        vm_stor = primary_disk.name

        # Find a dir-type storage for downloading (download-url requires
        # dir/nfs/cifs/cephfs with 'import' content type, not rbd/zfs).
        dl_stor = vm_stor
        for s in node.storage.get():
            if s['type'] in ('dir', 'nfs', 'cifs', 'cephfs') and 'import' in s.get('content', ''):
                dl_stor = s['storage']
                break

        # Extract filename from URL; Proxmox download-url requires a
        # recognised disk extension (.qcow2, .raw, .vmdk, .iso).  Cloud
        # images often use ".img" which is typically QCOW2 — rename to
        # .qcow2 so Proxmox accepts it.
        filename = template.source_url.rstrip('/').split('/')[-1]
        if filename.endswith('.img'):
            filename = filename[:-4] + '.qcow2'

        # Remove any leftover import file from a previous attempt
        volid = f'{dl_stor}:import/{filename}'
        try:
            node.storage(dl_stor).content.delete(volid)
            logger.info(f"Removed stale import file {volid}")
        except ResourceException:
            pass

        # Download image to node storage
        logger.info(f"Downloading {filename} to {target_node.name}:{dl_stor}")
        upid = node.storage(dl_stor)('download-url').post(
            content='import', filename=filename, url=template.source_url,
        )
        _wait_for_proxmox_task(node, upid)

        # Reserve VMID
        vmid = proxmox.cluster.nextid.get()
        logger.info(f"Creating template VM {vmid} on {target_node.name}")

        # Create VM with imported disk on primary storage.
        # Sanitise name — Proxmox requires valid DNS hostname.
        vm_name = re.sub(r'[^a-zA-Z0-9\-]', '-', template.name).strip('-')[:63]
        create_upid = node.qemu.post(
            vmid=vmid,
            name=vm_name,
            scsi0=f'{vm_stor}:0,import-from={dl_stor}:import/{filename}',
            ide2=f'{vm_stor}:cloudinit',
            serial0='socket',
            vga='serial0',
            boot='order=scsi0',
            agent='enabled=1',
            ostype='l26',
            scsihw='virtio-scsi-single',
        )
        _wait_for_proxmox_task(node, create_upid)

        # Convert to template
        logger.info(f"Converting VM {vmid} to template")
        node.qemu(vmid).template.post()

        template.file = str(vmid)
        template.status = 'ready'
        template.status_msg = ''
        template.save()
        logger.info(f"KVM template {template_id} imported successfully as VMID {vmid}")

    except NodeDisk.DoesNotExist:
        error_msg = f"No primary storage disk configured for node {target_node.name}"
        logger.error(f"Failed to import template {template_id}: {error_msg}")
        template.status = 'error'
        template.status_msg = error_msg
        template.save()
        raise
    except ConnectionError as e:
        error_msg = f"Cannot connect to Proxmox cluster at {cluster.host}"
        logger.error(f"Failed to import template {template_id}: {error_msg} - {str(e)}")
        template.status = 'error'
        template.status_msg = error_msg
        template.save()
        raise
    except ResourceException as e:
        error_msg = f"Proxmox API error: {str(e)}"
        logger.error(f"Failed to import template {template_id}: {error_msg}")
        template.status = 'error'
        template.status_msg = error_msg
        template.save()
        raise
    except Exception as e:
        error_msg = f"Unexpected error during import: {str(e)}"
        logger.error(f"Failed to import template {template_id}: {error_msg}", exc_info=True)
        template.status = 'error'
        template.status_msg = str(e)
        template.save()
        raise


@shared_task(base=Singleton, lock_expiry=60 * 15)
def sync_kvm_templates():
    """
    Periodic task to ensure KVM cloud image templates are available.
    Re-imports missing or failed templates.
    """
    logger.info("Starting KVM template sync")
    kvm_templates = Template.objects.filter(type='kvm').exclude(source_url='')
    if not kvm_templates.exists():
        logger.info("No KVM cloud image templates registered — nothing to sync")
        return

    checked = 0
    reimported = 0
    errors = 0

    for template in kvm_templates:
        checked += 1

        # Retry pending/error templates
        if template.status in ('pending', 'error'):
            logger.info(f"Retrying import for template {template.id} ({template.name})")
            import_kvm_template.delay(template.id)
            reimported += 1
            continue

        # For ready templates, verify the VM still exists in the cluster
        if template.status == 'ready' and template.file and template.node:
            try:
                cluster = template.node.cluster
                proxmox = ProxmoxAPI(
                    cluster.host, user=cluster.user, token_name='inveterate',
                    token_value=cluster.key, verify_ssl=False, port=8006,
                )
                vmid = int(template.file)
                found = any(
                    r['vmid'] == vmid
                    for r in proxmox.cluster.resources.get(type='vm')
                )
                if not found:
                    logger.warning(
                        f"Template VM {vmid} missing for template {template.id} ({template.name}), re-importing"
                    )
                    template.file = ''
                    template.status = 'pending'
                    template.status_msg = 'Template VM missing from cluster'
                    template.save()
                    import_kvm_template.delay(template.id)
                    reimported += 1
            except ConnectionError as e:
                logger.error(f"Cannot connect to verify template {template.id}: {e}")
                errors += 1
            except Exception as e:
                logger.error(f"Error checking template {template.id}: {e}", exc_info=True)
                errors += 1

    logger.info(
        f"KVM template sync completed: {checked} checked, "
        f"{reimported} re-imported, {errors} errors"
    )


# ===================================================================
# NPM Sync Tasks
# ===================================================================

def _get_npm_client(gateway):
    from .npm import NPMClient
    return NPMClient(gateway.host, gateway.admin_email, gateway.admin_password)


@shared_task(base=Singleton, lock_expiry=60 * 15)
def sync_port_forward(port_forward_id):
    """Create or update the NPM stream for a PortForward record."""
    logger.info(f"Syncing port forward {port_forward_id} to NPM")
    pf = PortForward.objects.select_related(
        'port_block__gateway', 'port_block__service_network__ip'
    ).get(pk=port_forward_id)

    client = _get_npm_client(pf.port_block.gateway)
    forwarding_host = pf.port_block.service_network.ip.value
    tcp = pf.protocol in ('tcp', 'both')
    udp = pf.protocol in ('udp', 'both')

    try:
        if pf.npm_stream_id:
            client.update_stream(
                pf.npm_stream_id,
                incoming_port=pf.external_port,
                forwarding_host=forwarding_host,
                forwarding_port=pf.internal_port,
                tcp_forwarding=tcp,
                udp_forwarding=udp,
            )
            logger.info(f"Updated NPM stream {pf.npm_stream_id} for port forward {pf.id}")
        else:
            result = client.create_stream(
                incoming_port=pf.external_port,
                forwarding_host=forwarding_host,
                forwarding_port=pf.internal_port,
                tcp=tcp,
                udp=udp,
            )
            pf.npm_stream_id = result['id']
            pf.save(update_fields=['npm_stream_id'])
            logger.info(f"Created NPM stream {pf.npm_stream_id} for port forward {pf.id}")
    except Exception as e:
        logger.error(f"Failed to sync port forward {pf.id} to NPM: {e}")
        raise


@shared_task(base=Singleton, lock_expiry=60 * 15)
def sync_domain_route(domain_route_id):
    """Create or update the NPM proxy host for a DomainRoute record."""
    logger.info(f"Syncing domain route {domain_route_id} to NPM")
    dr = DomainRoute.objects.select_related('service').get(pk=domain_route_id)

    # Find the internal IP and gateway for this service
    internal_sn = ServiceNetwork.objects.filter(
        service=dr.service, ip__pool__internal=True
    ).select_related('ip', 'port_block__gateway').first()

    if not internal_sn or not hasattr(internal_sn, 'port_block'):
        logger.error(f"No internal IP with port block for domain route {dr.id}")
        return

    client = _get_npm_client(internal_sn.port_block.gateway)
    forward_host = internal_sn.ip.value

    try:
        if dr.npm_proxy_host_id:
            client.update_proxy_host(
                dr.npm_proxy_host_id,
                domain_names=[dr.domain],
                forward_host=forward_host,
                forward_port=dr.forward_port,
                ssl_forced=dr.force_ssl,
            )
            logger.info(f"Updated NPM proxy host {dr.npm_proxy_host_id} for domain route {dr.id}")
        else:
            result = client.create_proxy_host(
                domain=dr.domain,
                forward_host=forward_host,
                forward_port=dr.forward_port,
                ssl=dr.ssl,
                force_ssl=dr.force_ssl,
            )
            dr.npm_proxy_host_id = result['id']
            dr.save(update_fields=['npm_proxy_host_id'])
            logger.info(f"Created NPM proxy host {dr.npm_proxy_host_id} for domain route {dr.id}")
    except Exception as e:
        logger.error(f"Failed to sync domain route {dr.id} to NPM: {e}")
        raise


@shared_task(base=Singleton, lock_expiry=60 * 15)
def delete_npm_stream(gateway_id, npm_stream_id):
    """Fire-and-forget cleanup of an NPM stream."""
    logger.info(f"Deleting NPM stream {npm_stream_id} on gateway {gateway_id}")
    try:
        gw = PortGateway.objects.get(pk=gateway_id)
        client = _get_npm_client(gw)
        client.delete_stream(npm_stream_id)
        logger.info(f"Deleted NPM stream {npm_stream_id}")
    except PortGateway.DoesNotExist:
        logger.warning(f"Gateway {gateway_id} not found, cannot delete stream {npm_stream_id}")
    except Exception as e:
        logger.warning(f"Failed to delete NPM stream {npm_stream_id}: {e}")


@shared_task(base=Singleton, lock_expiry=60 * 15)
def delete_npm_proxy_host(gateway_id, npm_proxy_host_id):
    """Fire-and-forget cleanup of an NPM proxy host."""
    logger.info(f"Deleting NPM proxy host {npm_proxy_host_id} on gateway {gateway_id}")
    try:
        gw = PortGateway.objects.get(pk=gateway_id)
        client = _get_npm_client(gw)
        client.delete_proxy_host(npm_proxy_host_id)
        logger.info(f"Deleted NPM proxy host {npm_proxy_host_id}")
    except PortGateway.DoesNotExist:
        logger.warning(f"Gateway {gateway_id} not found, cannot delete proxy host {npm_proxy_host_id}")
    except Exception as e:
        logger.warning(f"Failed to delete NPM proxy host {npm_proxy_host_id}: {e}")
