import logging
import time
import traceback
from datetime import datetime
from django.conf import settings
from celery import shared_task
from celery_singleton import Singleton
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django_celery_results.models import TaskResult
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

from .blesta.api import BlestaApi
from .blesta.objects import BlestaUser, BlestaPlan
from .models import Node, Plan, Inventory, Service, ServiceBandwidth, BillingType, Cluster, IP, ServiceNetwork, IPPool, NodeDisk

if settings.STRIPE_LIVE_SECRET_KEY or settings.STRIPE_TEST_SECRET_KEY:
    import stripe
    import djstripe.settings
    from djstripe.models import Product, Price, Customer

logger = logging.getLogger()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def calculate_inventory():
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


@shared_task(base=Singleton, lock_expiry=60 * 15)
def assign_ips(service_id):
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
    service = Service.objects.get(pk=service_id)
    proxmox = ProxmoxAPI(service.node.cluster.host, user=service.node.cluster.user, token_name='inveterate',
                         token_value=service.node.cluster.key,
                         verify_ssl=False, port=8006, timeout=600)
    node = proxmox.nodes(service.node)
    service_type = service.service_plan.type
    try:
        proxmox.pools.post(poolid="inveterate")
    except ResourceException:
        pass

    # If you got no storage you get some storage
    if not service.service_plan.storage:
        service.service_plan.storage = NodeDisk.objects.get(node=service.node, primary=True)

    service.machine_id = f"1{service.id:06}"
    try:
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
        assign_ips(service_id)
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

        service_bandwidth, created = ServiceBandwidth.objects.get_or_create(service=service)
        if created:
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
    except Exception as e:
        service.status = "error"
        service.status_msg = str(e)
    else:
        service.status = "active"
        service.status_msg = None
    service.save()
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
    machine, service = get_vm(service_id)
    machine.status.start.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def stop_vm(service_id):
    machine, service = get_vm(service_id)
    machine.status.stop.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def reset_vm(service_id):
    machine, service = get_vm(service_id)
    machine.status.reset.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def shutdown_vm(service_id):
    machine, service = get_vm(service_id)
    machine.status.shutdown.post()


@shared_task(base=Singleton, lock_expiry=60 * 15)
def reboot_vm(service_id):
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
        "bandwidth_max": service.service_plan.bandwidth * 1024 * 1024,
        "bandwidth_used": service.bandwidth.bandwidth + service.bandwidth.bandwidth_banked
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


def get_vm_tasks(service_id):
    task_objects = TaskResult.objects.filter(task_args__startswith=f"\"('{service_id}',").order_by('-date_done')
    tasks = []
    for task in task_objects:
        task_data = {
            "id": task.task_id,
            "name": task.task_name,
            "date": task.date_done
        }
        tasks.append(task_data)
    return tasks


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
    blesta_instances = BillingType.objects.all().filter(type='blesta')
    for instance in blesta_instances:
        if instance.mirror is False or service.billing_type.id == instance.id:
            continue
        billing_backend = instance.backend
        blesta = BlestaApi(server=billing_backend.host, user=billing_backend.user, key=billing_backend.key)
        try:
            company_id = blesta.get_company_by_hostname(billing_backend.company_hostname)["id"]
            modules = blesta.get_all_modules(company_id)
            module_id = None
            for module in modules:
                if module["class"] == "universal_module":
                    module_id = module["id"]
            services = blesta.search_field(module_id, 'inveterate_id', service_id)
            if len(services) == 1:
                blesta.cancel_service(service_id=services[0]['id'], cancel_date=cancel_date)
        except ConnectionError:
            traceback.print_exc()
            continue


@shared_task(base=Singleton, lock_expiry=60 * 15)
def meter_bandwidth():
    api_objects = {}
    for service in Service.objects.all().filter(status="active"):
        node_name = service.node.name
        if node_name not in api_objects:
            api_objects[node_name] = ProxmoxAPI(service.node.cluster.host, user=service.node.cluster.user,
                                                token_name='inveterate', token_value=service.node.cluster.key,
                                                verify_ssl=False, port=8006)
        node = api_objects[node_name].nodes(node_name)

        now = timezone.now()
        try:
            bandwidth = ServiceBandwidth.objects.get(id=service.bandwidth_id)
        except ServiceBandwidth.DoesNotExist:
            continue
        if now > bandwidth.renewal_dtm:
            start = now
            bandwidth.renewal_dtm = start + relativedelta(months=1)
            bandwidth.bandwidth_stale += bandwidth.bandwidth
            bandwidth.bandwidth_banked = 0

        if service.service_plan.type == "lxc":
            machine = node.lxc(service.machine_id)
        elif service.service_plan.type == "kvm":
            machine = node.qemu(service.machine_id)

        data = machine.status.current.get()
        tick = data["uptime"]
        if tick > bandwidth.system_tick:
            try:
                bandwidth.bandwidth = data["netin"] + data["netout"]
            except KeyError as e:
                logger.info(e)
        elif tick < bandwidth.system_tick:
            banked = bandwidth.bandwidth - bandwidth.bandwidth_stale
            bandwidth.bandwidth_banked += banked
            bandwidth.bandwidth = 0
            bandwidth.bandwidth_stale = 0
            try:
                bandwidth.bandwidth = data["netin"] + data["netout"]
            except KeyError as e:
                logger.info(e)
        bandwidth.system_tick = tick
        bandwidth.save()


@shared_task(lock_expiry=60 * 15)
def provision_billing(service_id):
    service = Service.objects.get(pk=service_id)
    blesta_instances = BillingType.objects.all().filter(type='blesta')
    user = service.owner
    for instance in blesta_instances:
        if instance.mirror is False and service.billing_type.id != instance.id:
            continue
        billing_backend = instance.backend
        blesta = BlestaApi(server=billing_backend.host, user=billing_backend.user, key=billing_backend.key)
        blesta_user = BlestaUser(api=blesta, hostname=billing_backend.company_hostname, username=user.email,
                                 first_name=user.first_name, last_name=user.last_name)
        blesta_plan = BlestaPlan(api=blesta, hostname=billing_backend.company_hostname, name=service.plan.name,
                                 term=service.plan.term, period=service.plan.period, price=service.plan.price)
        billing_id = blesta.add_client_service(blesta_user.client_id, blesta_plan.pricing_id, blesta_plan.package_id)
        svc_id = service.id
        blesta.set_inveterate_id(service_id=billing_id, inveterate_id=svc_id)
        blesta.create_service_invoice(blesta_user.client_id, billing_id)
        if service.billing_type.id == instance.id:
            service.billing_id = billing_id
            service.save()

    stripe_instances = BillingType.objects.all().filter(type='stripe')
    for instance in stripe_instances:
        if service.billing_type.id != instance.id:
            continue
        Customer.get_or_create(service.owner)
        try:
            product = Product.objects.get(livemode=djstripe.settings.STRIPE_LIVE_MODE,
                                          name=service.plan.name,
                                          active=True)
        except Product.DoesNotExist:
            new_product = {
                'name': service.plan.name,
                'active': True
            }
            stripe.api_key = djstripe.settings.STRIPE_SECRET_KEY
            stripe_product = stripe.Product.create(**new_product)
            product = Product._create_from_stripe_object(data=stripe_product)

        try:
            Price.objects.get(livemode=djstripe.settings.STRIPE_LIVE_MODE,
                              active=True,
                              product=product,
                              billing_scheme='per_unit',
                              unit_amount=int(service.plan.price * 100),
                              recurring__interval=service.plan.period,
                              recurring__interval_count=service.plan.term
                              )
        except Price.DoesNotExist:
            new_price = {
                'active': True,
                'currency': 'usd',
                'product': product.id,
                'billing_scheme': 'per_unit',
                'unit_amount': int(service.plan.price * 100),
                "recurring": {
                    "aggregate_usage": None,
                    "interval": service.plan.period,
                    "interval_count": service.plan.term,
                    "usage_type": "licensed"
                },
            }
            stripe.api_key = djstripe.settings.STRIPE_SECRET_KEY
            stripe_price = stripe.Price.create(**new_price)
            Price._create_from_stripe_object(data=stripe_price)


@shared_task()
def record_payment(service_id, amt, currency, reference_id):
    service = Service.objects.get(pk=service_id)
    blesta_instances = BillingType.objects.all().filter(type='blesta')
    user = service.owner
    for instance in blesta_instances:
        if instance.mirror is False or service.billing_type.id == instance.id:
            continue
        billing_backend = instance.backend
        blesta = BlestaApi(server=billing_backend.host, user=billing_backend.user, key=billing_backend.key)
        try:
            blesta_user = blesta.search_user(user.email)
            client_id = blesta.get_client_from_user(blesta_user["id"])["id"]
            transactions = [trans for trans in blesta.search_transactions(reference_id) if
                            trans["status"] == "approved"]
            if len(transactions) == 1:
                transaction_id = transactions[0]["id"]
            else:
                transaction_id = blesta.record_transaction(client_id=client_id, amount=amt, currency=currency,
                                                           reference_id=reference_id)
            company_id = blesta.get_company_by_hostname(billing_backend.company_hostname)["id"]
            modules = blesta.get_all_modules(company_id)
            module_id = None
            for module in modules:
                if module["class"] == "universal_module":
                    module_id = module["id"]
            services = blesta.search_field(module_id, 'inveterate_id', service_id)
            if len(services) == 1:
                invoices = blesta.get_service_invoices(services[0]["id"])
                if len(invoices) > 0:
                    blesta.apply_transaction(transaction_id=transaction_id, invoice_id=invoices[0]["id"], amount=amt)

        except ConnectionError:
            traceback.print_exc()
            continue


@shared_task()
def set_service_renewal(service_id, renewal_dtm):
    service = Service.objects.get(pk=service_id)
    blesta_instances = BillingType.objects.all().filter(type='blesta')
    for instance in blesta_instances:
        if instance.mirror is False or service.billing_type.id == instance.id:
            continue
        billing_backend = instance.backend
        blesta = BlestaApi(server=billing_backend.host, user=billing_backend.user, key=billing_backend.key)
        try:
            company_id = blesta.get_company_by_hostname(billing_backend.company_hostname)["id"]
            modules = blesta.get_all_modules(company_id)
            module_id = None
            for module in modules:
                if module["class"] == "universal_module":
                    module_id = module["id"]
            services = blesta.search_field(module_id, 'inveterate_id', service_id)
            if len(services) == 1:
                services[0]["date_renews"] = datetime.strftime(renewal_dtm, '%Y-%m-%d %H:%M:%S')
                blesta.edit_service(service_id=services[0]['id'], service_data=services[0])
                blesta.set_inveterate_id(service_id=services[0]['id'], inveterate_id=service.id)
        except ConnectionError:
            traceback.print_exc()
            continue


@shared_task()
def test_task():
    print("HI!")
    return True
