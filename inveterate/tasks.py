import logging
import time
import traceback
from datetime import datetime
from sqlite3 import IntegrityError

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

from .blesta.api import BlestaApi
from .blesta.objects import BlestaUser, BlestaPlan
from .models import Node, Plan, Inventory, Service, ServiceBandwidth, Cluster, IP, ServiceNetwork, IPPool, NodeDisk

logger = logging.getLogger(__name__)


@shared_task(base=Singleton, lock_expiry=60 * 15)
def calculate_inventory():
    logger.info("Starting inventory calculation")
    plans = Plan.objects.all()
    nodes = Node.objects.all()
    inventory_fields = ['cores', 'ram', 'swap', 'size', 'bandwidth']
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
            inventory, created = Inventory.objects.get_or_create(plan=plan, node=node)
            inventory.quantity = lowest
            inventory.save()
            logger.debug(f"Node {node.name}, Plan {plan.name}: {inventory.quantity} slots available")
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

    service.machine_id = f"1{service.id:06}"
    try:
        logger.debug(f"Assigning IPs for service {service_id}")
        assign_ips(service_id)
        logger.debug(f"IP assignment completed for service {service_id}")

        if service_type == "kvm":
            clone_data = {
                'newid': service.machine_id,
                'storage': service.service_plan.storage.name,
                'full': 1,
                'target': service.node.name
                # 'pool': 'inveterate'
            }
            clone_node = node
            try:
                kvm_templates = proxmox.pools('templates').get()
            except ResourceException:
                pass
            else:
                if "members" in kvm_templates:
                    for member in kvm_templates["members"]:
                        if member["vmid"] != int(service.service_plan.template.file):
                            continue
                        else:
                            clone_node = proxmox.nodes(member["node"])
                            break
            #TODO: create vm on clone node and then migrate
            try:
                clone_node.qemu(service.service_plan.template.file).clone.post(**clone_data)
                lock = True
                while lock:
                    try:
                        status = node.qemu(service.machine_id).status.current.get()
                    except ResourceException as e:
                        status = clone_node(service.machine_id).status.current.get()
                    if "lock" not in status:
                        lock = False
                    else:
                        time.sleep(1)
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
        if service_type == "lxc":
            vm_data = {
                'ostemplate': f'local:vztmpl/{service.service_plan.template.file}',
                'hostname': service.hostname,
                'storage': 'local-lvm',
                'memory': service.service_plan.ram,
                'swap': service.service_plan.swap,
                'cores': service.service_plan.cores,
                'rootfs': f'{service.service_plan.size}',
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
                'firewall': firewall
            }
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

        try:
            service_bandwidth = ServiceBandwidth.objects.get(service=service)
        except ServiceBandwidth.DoesNotExist:
            service_bandwidth = ServiceBandwidth.objects.create(bandwidth=10240)
            now = datetime.now()
            service_bandwidth.renewal_dtm = now + relativedelta(months=1)
            service_bandwidth.save()

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
            node.lxc.create(vmid=service.machine_id, **vm_data)
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

        proxmox.pools("inveterate").put(vms=service.machine_id)
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
    service = Service.objects.get(pk=service_id)
    proxmox = ProxmoxAPI(service.node.cluster.host, user=service.node.cluster.user, token_name='inveterate',
                         token_value=service.node.cluster.key,
                         verify_ssl=False, port=8006)
    node = proxmox.nodes(service.node)
    machine = None
    if service.service_plan.type == "kvm":
        machine = node.qemu(service.machine_id)
    if service.service_plan.type == "lxc":
        machine = node.lxc(service.machine_id)
    return machine, service


def get_service_node(service_id):
    service = Service.objects.get(pk=service_id)
    proxmox = ProxmoxAPI(service.node.cluster.host, user=service.node.cluster.user, token_name='inveterate',
                         token_value=service.node.cluster.key,
                         verify_ssl=False, port=8006)
    node = proxmox.nodes(service.node)
    return node


def get_cluster(cluster_id):
    cluster = Cluster.objects.get(pk=cluster_id)
    proxmox = ProxmoxAPI(cluster.host, user=cluster.user, token_name='inveterate',
                         token_value=cluster.key,
                         verify_ssl=False, port=8006)
    cluster_obj = proxmox.cluster
    return cluster_obj


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
        #"bandwidth_used": service.bandwidth.bandwidth + service.bandwidth.bandwidth_banked
    }
    return stats


def get_vm_ips(service_id):
    networks = ServiceNetwork.objects.filter(service_id=service_id)
    ips = []
    for network in networks:
        ip = {
            "value": network.ip.value
        }
        if network.net_id == 0:
            ip["primary"] = True
        else:
            ip["primary"] = False
        ips.append(ip)
    return ips


# def get_vm_tasks(service_id):
#     task_objects = TaskResult.objects.filter(task_args__startswith=f"\"('{service_id}',").order_by('-date_done')
#     tasks = []
#     for task in task_objects:
#         task_data = {
#             "id": task.task_id,
#             "name": task.task_name,
#             "date": task.date_done
#         }
#         tasks.append(task_data)
#     return tasks


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
def cancel_service(service_id, cancel_date=datetime.now()):
    machine, service = get_vm(service_id)
    machine.delete(force=1)
    service.status = "destroyed"
    service.save()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def meter_bandwidth():
    logger.info("Starting bandwidth metering")
    api_objects = {}
    bandwidths_to_update = []
    now = timezone.now()

    # Optimize query with select_related to avoid N+1 queries
    services = Service.objects.filter(status="active").select_related(
        'node', 'node__cluster', 'service_plan', 'bandwidth'
    )

    services_processed = 0
    services_failed = 0

    for service in services:
        try:
            # Skip if no bandwidth tracking
            if not service.bandwidth_id:
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

            bandwidth = service.bandwidth

            # Handle bandwidth renewal
            if now > bandwidth.renewal_dtm:
                bandwidth.renewal_dtm = now + relativedelta(months=1)
                bandwidth.bandwidth_stale += bandwidth.bandwidth
                bandwidth.bandwidth_banked = 0
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

            if tick > bandwidth.system_tick:
                try:
                    bandwidth.bandwidth = data["netin"] + data["netout"]
                except KeyError as e:
                    logger.warning(f"Missing network data for service {service.id}: {e}")
            elif tick < bandwidth.system_tick:
                # VM was restarted
                banked = bandwidth.bandwidth - bandwidth.bandwidth_stale
                bandwidth.bandwidth_banked += banked
                bandwidth.bandwidth = 0
                bandwidth.bandwidth_stale = 0
                try:
                    bandwidth.bandwidth = data["netin"] + data["netout"]
                except KeyError as e:
                    logger.warning(f"Missing network data for service {service.id}: {e}")

            bandwidth.system_tick = tick
            bandwidths_to_update.append(bandwidth)
            services_processed += 1

        except ResourceException as e:
            logger.error(f"Proxmox API error for service {service.id}: {str(e)}")
            services_failed += 1
        except Exception as e:
            logger.error(f"Failed to meter bandwidth for service {service.id}: {str(e)}", exc_info=True)
            services_failed += 1

    # Bulk update all bandwidth records
    if bandwidths_to_update:
        ServiceBandwidth.objects.bulk_update(
            bandwidths_to_update,
            ['bandwidth', 'bandwidth_stale', 'bandwidth_banked', 'system_tick', 'renewal_dtm']
        )
        logger.info(f"Bandwidth metering completed: {services_processed} services processed, {services_failed} failed, {len(bandwidths_to_update)} updated")
    else:
        logger.info("No bandwidth data to update")


@shared_task(base=Singleton, lock_expiry=60 * 15)
def cleanup_console_users():
    """
    Clean up orphaned Proxmox console users for deleted services.
    Console users are created with pattern: inveterate{owner_id}@pve
    """
    logger.info("Starting console user cleanup")

    # Get all active service owner IDs
    active_owner_ids = set(
        Service.objects.exclude(status='destroyed')
        .values_list('owner_id', flat=True)
        .distinct()
    )

    cleaned_up = 0
    errors = 0

    # Process each cluster
    for cluster in Cluster.objects.all():
        try:
            proxmox = ProxmoxAPI(
                cluster.host,
                user=cluster.user,
                token_name='inveterate',
                token_value=cluster.key,
                verify_ssl=False,
                port=8006,
                timeout=30
            )

            # Get all users
            users = proxmox.access.users.get()

            for user in users:
                userid = user.get('userid', '')

                # Check if this is an inveterate console user
                if userid.startswith('inveterate') and userid.endswith('@pve'):
                    # Extract owner_id from userid (format: inveterate{owner_id}@pve)
                    try:
                        owner_id_str = userid.replace('inveterate', '').replace('@pve', '')
                        owner_id = int(owner_id_str)

                        # Delete if owner has no active services
                        if owner_id not in active_owner_ids:
                            proxmox.access.users(userid).delete()
                            logger.info(f"Deleted orphaned console user: {userid}")
                            cleaned_up += 1
                    except (ValueError, IndexError):
                        logger.warning(f"Could not parse owner_id from console user: {userid}")

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
