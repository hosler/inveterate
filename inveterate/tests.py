from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from .models import (
    Cluster, Node, NodeDisk, Plan, ServicePlan, Service,
    Template, IPPool, IP, ServiceNetwork, Inventory,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cluster(**kw):
    defaults = dict(name='test-cluster', host='10.0.0.1', user='root@pam', key='tok')
    defaults.update(kw)
    return Cluster.objects.create(**defaults)


def _node(cluster=None, **kw):
    if cluster is None:
        cluster = _cluster()
    defaults = dict(
        name='pve1', cluster=cluster,
        size=500, ram=65536, swap=65536, cores=32, bandwidth=10240,
    )
    defaults.update(kw)
    return Node.objects.create(**defaults)


def _disk(node, **kw):
    defaults = dict(name='local-lvm', size=500, primary=True, shared=False)
    defaults.update(kw)
    return NodeDisk.objects.create(node=node, **defaults)


def _plan(**kw):
    defaults = dict(
        name='VPS-1', size=10, ram=1024, swap=512, cores=2,
        bandwidth=1024, cpu_units=1024, cpu_limit=Decimal('1.00'),
        ipv4_ips=1, ipv6_ips=0, internal_ips=0,
    )
    defaults.update(kw)
    return Plan.objects.create(**defaults)


def _template(**kw):
    defaults = dict(name='debian-12', type='lxc', file='debian-12-standard_12.2-1_amd64.tar.zst')
    defaults.update(kw)
    return Template.objects.create(**defaults)


def _service(owner, node, service_plan, **kw):
    defaults = dict(hostname='test.example.com', status='active')
    defaults.update(kw)
    return Service.objects.create(owner=owner, node=node, service_plan=service_plan, **defaults)


def _service_plan(template=None, storage=None, **kw):
    defaults = dict(
        name='VPS-1', type='lxc', size=10, ram=1024, swap=512, cores=2,
        bandwidth=1024, cpu_units=1024, cpu_limit=Decimal('1.00'),
        ipv4_ips=1, ipv6_ips=0, internal_ips=0,
    )
    defaults.update(kw)
    return ServicePlan.objects.create(template=template, storage=storage, **defaults)


def _ip_pool(node, **kw):
    defaults = dict(
        name='public-v4', type='ipv4', network='10.0.0.0', mask=24,
        gateway='10.0.0.1', dns='8.8.8.8', internal=False,
    )
    defaults.update(kw)
    pool = IPPool.objects.create(**defaults)
    pool.nodes.add(node)
    return pool


def _admin():
    return User.objects.create_superuser('admin', 'admin@test.com', 'pass')


def _user():
    return User.objects.create_user('user1', 'user1@test.com', 'pass')


# ===================================================================
# TestModels
# ===================================================================

class TestModels(TestCase):

    def test_service_bw_defaults(self):
        user = _admin()
        node = _node()
        sp = _service_plan()
        svc = _service(user, node, sp)
        self.assertEqual(svc.bw_usage, 0)
        self.assertEqual(svc.bw_banked, 0)
        self.assertEqual(svc.bw_stale, 0)
        self.assertEqual(svc.bw_system_tick, 0)
        self.assertIsNone(svc.bw_renewal_dtm)

    def test_service_delete_cascades_to_service_plan(self):
        user = _admin()
        node = _node()
        sp = _service_plan()
        sp_id = sp.id
        svc = _service(user, node, sp)
        svc.delete()
        self.assertFalse(ServicePlan.objects.filter(pk=sp_id).exists())

    def test_service_plan_name(self):
        sp = _service_plan(name='Custom Plan')
        self.assertEqual(sp.name, 'Custom Plan')

    def test_nodedisk_unique_primary_constraint(self):
        node = _node()
        _disk(node, name='disk1', primary=True)
        with self.assertRaises(IntegrityError):
            _disk(node, name='disk2', primary=True)

    def test_nodedisk_multiple_non_primary(self):
        node = _node()
        _disk(node, name='disk1', primary=False)
        _disk(node, name='disk2', primary=False)
        self.assertEqual(NodeDisk.objects.filter(node=node, primary=False).count(), 2)

    def test_nodedisk_shared_default_false(self):
        node = _node()
        d = _disk(node)
        self.assertFalse(d.shared)


# ===================================================================
# TestServiceSerializer
# ===================================================================

class TestServiceSerializer(TestCase):

    def setUp(self):
        self.user = _admin()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.disk = _disk(self.node)
        self.plan = _plan()
        self.template = _template()
        # Create inventory so auto-node-select works
        Inventory.objects.create(plan=self.plan, node=self.node, quantity=5)
        self.factory = APIRequestFactory()

    @patch('inveterate.serializers.provision_service')
    def test_create_snapshots_plan_fields(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'snap.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        self.assertTrue(ser.is_valid(), ser.errors)
        svc = ser.save()
        sp = svc.service_plan
        self.assertEqual(sp.name, self.plan.name)
        self.assertEqual(sp.ram, self.plan.ram)
        self.assertEqual(sp.cores, self.plan.cores)
        self.assertEqual(sp.size, self.plan.size)
        self.assertEqual(sp.bandwidth, self.plan.bandwidth)

    @patch('inveterate.serializers.provision_service')
    def test_create_plan_not_saved_on_service(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'nofk.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        ser.is_valid(raise_exception=True)
        svc = ser.save()
        # Service should NOT have a direct 'plan' FK (it was removed)
        self.assertFalse(hasattr(svc, 'plan'))

    @patch('inveterate.serializers.provision_service')
    def test_create_sets_storage_to_primary_disk(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'disk.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        ser.is_valid(raise_exception=True)
        svc = ser.save()
        self.assertEqual(svc.service_plan.storage, self.disk)

    @patch('inveterate.serializers.provision_service')
    def test_create_auto_selects_node(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'auto.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
            # no 'node' provided
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        ser.is_valid(raise_exception=True)
        svc = ser.save()
        self.assertEqual(svc.node, self.node)

    @patch('inveterate.serializers.provision_service')
    def test_plan_name_read_field(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'name.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        ser.is_valid(raise_exception=True)
        svc = ser.save()
        # Re-serialize to check plan_name
        out = ServiceSerializer(svc, context={'request': request})
        self.assertEqual(out.data['plan_name'], 'VPS-1')

    def test_hostname_validation_valid(self):
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'valid.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_hostname_validation_invalid(self):
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': '-not-valid',
            'plan': self.plan.id,
            'template': self.template.name,
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        self.assertFalse(ser.is_valid())
        self.assertIn('hostname', ser.errors)


# ===================================================================
# TestCalculateInventory
# ===================================================================

class TestCalculateInventory(TestCase):

    def test_empty_node(self):
        from .tasks import calculate_inventory
        node = _node()
        disk = _disk(node, size=500)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # limiting factor: size → 500/10=50, ram → 65536/1024=64, cores → 32/2=16, bw → 10240/1024=10
        self.assertEqual(inv.quantity, 10)

    def test_node_with_services(self):
        from .tasks import calculate_inventory
        user = _admin()
        node = _node()
        disk = _disk(node, size=500)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024)
        # Create 5 services consuming resources
        for i in range(5):
            sp = _service_plan(storage=disk, size=10, ram=1024, cores=2, bandwidth=1024)
            _service(user, node, sp, hostname=f's{i}.example.com')
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # bandwidth was limiting: (10240 - 5*1024)/1024 = 5
        self.assertEqual(inv.quantity, 5)

    def test_shared_disk_accounting(self):
        from .tasks import calculate_inventory
        user = _admin()
        cluster = _cluster()
        node1 = _node(cluster=cluster, name='pve1')
        node2 = _node(cluster=cluster, name='pve2')
        # Both nodes share a Ceph disk
        disk1 = _disk(node1, name='ceph-pool', size=100, shared=True)
        disk2 = _disk(node2, name='ceph-pool', size=100, shared=True)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024)
        # Service on node1 using shared storage
        sp = _service_plan(storage=disk1, size=10, ram=1024, cores=2, bandwidth=1024)
        _service(user, node1, sp, hostname='s1.example.com')
        calculate_inventory()
        # Node2 shared disk should see the usage from node1
        inv2 = Inventory.objects.get(plan=plan, node=node2)
        # disk slots for node2: (100 - 10) / 10 = 9  (shared sees node1's usage)
        # bandwidth: 10240/1024 = 10, ram: 65536/1024 = 64, cores: 32/2 = 16
        # lowest is 9 (disk)
        self.assertEqual(inv2.quantity, 9)

    def test_local_disk_accounting(self):
        from .tasks import calculate_inventory
        user = _admin()
        cluster = _cluster()
        node1 = _node(cluster=cluster, name='pve1')
        node2 = _node(cluster=cluster, name='pve2')
        disk1 = _disk(node1, name='local-lvm', size=100, shared=False)
        disk2 = _disk(node2, name='local-lvm', size=100, shared=False)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024)
        # Service on node1 only
        sp = _service_plan(storage=disk1, size=10, ram=1024, cores=2, bandwidth=1024)
        _service(user, node1, sp, hostname='s1.example.com')
        calculate_inventory()
        # Node2 local disk should NOT see node1's usage
        inv2 = Inventory.objects.get(plan=plan, node=node2)
        # disk: 100/10=10, bw: 10240/1024=10
        self.assertEqual(inv2.quantity, 10)

    def test_zero_plan_field_no_crash(self):
        from .tasks import calculate_inventory
        node = _node()
        _disk(node, size=500)
        plan = _plan(bandwidth=0)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # bandwidth=0 → ZeroDivisionError handled → inf, not the bottleneck
        self.assertGreaterEqual(inv.quantity, 0)

    def test_node_without_primary_disk(self):
        from .tasks import calculate_inventory
        node = _node()
        # No disk at all
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # disk not factored in, bandwidth is bottleneck: 10240/1024=10
        self.assertEqual(inv.quantity, 10)


# ===================================================================
# TestProvisionService
# ===================================================================

class TestProvisionService(TestCase):

    def _setup_service(self, svc_type='lxc'):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type=svc_type, file='100' if svc_type == 'kvm' else 'debian.tar.zst')
        sp = _service_plan(template=tpl, storage=disk, type=svc_type)
        svc = _service(user, node, sp, status='pending')
        return svc

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.ProxmoxAPI')
    def test_lxc_provisioning_uses_storage_name(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        from .tasks import provision_service
        provision_service(svc.id, 'testpass')

        # Check lxc.create was called
        mock_node.lxc.create.assert_called_once()
        call_kwargs = mock_node.lxc.create.call_args[1]
        self.assertEqual(call_kwargs['storage'], 'local-lvm')
        self.assertEqual(call_kwargs['rootfs'], f'local-lvm:{svc.service_plan.size}')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.ProxmoxAPI')
    def test_lxc_sets_status_active(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        from .tasks import provision_service
        provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.ProxmoxAPI')
    def test_sets_bw_renewal_dtm(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        self.assertIsNone(svc.bw_renewal_dtm)
        from .tasks import provision_service
        provision_service(svc.id, 'testpass')
        svc.refresh_from_db()
        self.assertIsNotNone(svc.bw_renewal_dtm)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.ProxmoxAPI')
    def test_connection_error_sets_error_status(self, mock_cls, _mock_inv):
        from requests.exceptions import ConnectionError
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # ConnectionError inside the main try block (lxc.create)
        mock_node.lxc.create.side_effect = ConnectionError("refused")

        svc = self._setup_service('lxc')
        from .tasks import provision_service
        with self.assertRaises(ConnectionError):
            provision_service(svc.id, 'testpass')
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.ProxmoxAPI')
    def test_resource_exception_sets_error_status(self, mock_cls, _mock_inv):
        from proxmoxer.core import ResourceException
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        # pools.post succeeds (creating inveterate pool)
        mock_proxmox.pools.post.side_effect = ResourceException(500, 'exists', 'already exists')
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # lxc.create raises ResourceException
        mock_node.lxc.create.side_effect = ResourceException(500, 'fail', 'some error')

        svc = self._setup_service('lxc')
        from .tasks import provision_service
        with self.assertRaises(ResourceException):
            provision_service(svc.id, 'testpass')
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.ProxmoxAPI')
    def test_kvm_provisioning_calls_clone(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # Template pool lookup
        mock_proxmox.pools.return_value.get.return_value = {'members': []}
        # clone + status polling
        mock_node.qemu.return_value.status.current.get.return_value = {'status': 'stopped'}
        mock_node.qemu.return_value.firewall.rules.get.return_value = []
        mock_node.qemu.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('kvm')
        from .tasks import provision_service
        provision_service(svc.id, 'testpass')

        # clone.post should have been called
        mock_node.qemu.return_value.clone.post.assert_called_once()
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.ProxmoxAPI')
    def test_default_storage_fallback(self, mock_cls, _mock_inv):
        """When service_plan.storage is None, provision should grab primary disk and use it."""
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service('lxc')
        svc.service_plan.storage = None
        svc.service_plan.save()

        from .tasks import provision_service
        provision_service(svc.id, 'testpass')
        # Verify lxc.create was called with the primary disk's storage name
        mock_node.lxc.create.assert_called_once()
        call_kwargs = mock_node.lxc.create.call_args[1]
        self.assertEqual(call_kwargs['storage'], 'local-lvm')


# ===================================================================
# TestAssignIps
# ===================================================================

class TestAssignIps(TestCase):

    def test_assigns_correct_number_of_ips(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_v4 = _ip_pool(node, name='pub-v4', type='ipv4', internal=False)
        pool_v6 = _ip_pool(node, name='pub-v6', type='ipv6', network='2001:db8::', gateway='2001:db8::1', internal=False)
        pool_int = _ip_pool(node, name='internal', type='ipv4', network='192.168.0.0', gateway='192.168.0.1', internal=True)
        # Create IPs in each pool
        for i in range(5):
            IP.objects.create(pool=pool_v4, value=f'10.0.0.{10+i}')
            IP.objects.create(pool=pool_v6, value=f'2001:db8::{10+i}')
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        sp = _service_plan(storage=disk, ipv4_ips=2, ipv6_ips=1, internal_ips=1)
        svc = _service(user, node, sp)

        from .tasks import assign_ips
        assign_ips(svc.id)

        networks = ServiceNetwork.objects.filter(service=svc)
        self.assertEqual(networks.count(), 4)  # 2 + 1 + 1

        # Check types
        assigned = IP.objects.filter(owner__service=svc)
        v4_count = sum(1 for ip in assigned if ip.pool.type == 'ipv4' and not ip.pool.internal)
        v6_count = sum(1 for ip in assigned if ip.pool.type == 'ipv6')
        int_count = sum(1 for ip in assigned if ip.pool.internal)
        self.assertEqual(v4_count, 2)
        self.assertEqual(v6_count, 1)
        self.assertEqual(int_count, 1)

    def test_idempotent_skip_if_already_assigned(self):
        user = _admin()
        node = _node()
        disk = _disk(node)
        pool = _ip_pool(node)
        IP.objects.create(pool=pool, value='10.0.0.10')
        IP.objects.create(pool=pool, value='10.0.0.11')

        sp = _service_plan(storage=disk, ipv4_ips=1)
        svc = _service(user, node, sp)

        from .tasks import assign_ips
        assign_ips(svc.id)
        first_count = ServiceNetwork.objects.filter(service=svc).count()
        # Run again
        assign_ips(svc.id)
        second_count = ServiceNetwork.objects.filter(service=svc).count()
        self.assertEqual(first_count, second_count)


# ===================================================================
# TestMeterBandwidth
# ===================================================================

class TestMeterBandwidth(TestCase):

    @patch('inveterate.tasks.ProxmoxAPI')
    def test_normal_tick_increase(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine
        mock_machine.status.current.get.return_value = {
            'uptime': 100, 'netin': 5000, 'netout': 3000,
        }

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp, bw_system_tick=50,
                        bw_renewal_dtm=timezone.now() + timedelta(days=30))

        from .tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        self.assertEqual(svc.bw_usage, 8000)
        self.assertEqual(svc.bw_system_tick, 100)

    @patch('inveterate.tasks.ProxmoxAPI')
    def test_vm_restart_banks_correctly(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine
        mock_machine.status.current.get.return_value = {
            'uptime': 10, 'netin': 100, 'netout': 50,
        }

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp,
                        bw_system_tick=500, bw_usage=10000, bw_stale=2000, bw_banked=0,
                        bw_renewal_dtm=timezone.now() + timedelta(days=30))

        from .tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        # tick < system_tick → restart detected
        # banked += usage - stale = 10000 - 2000 = 8000
        self.assertEqual(svc.bw_banked, 8000)
        # bw_usage reset then set to netin+netout
        self.assertEqual(svc.bw_usage, 150)
        self.assertEqual(svc.bw_stale, 0)
        self.assertEqual(svc.bw_system_tick, 10)

    @patch('inveterate.tasks.ProxmoxAPI')
    def test_renewal_resets_bandwidth(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine
        mock_machine.status.current.get.return_value = {
            'uptime': 100, 'netin': 500, 'netout': 500,
        }

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp,
                        bw_system_tick=50, bw_usage=5000, bw_banked=1000,
                        bw_renewal_dtm=timezone.now() - timedelta(days=1))

        from .tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        # Renewal happened: stale += usage, banked = 0
        self.assertEqual(svc.bw_stale, 5000)
        self.assertEqual(svc.bw_banked, 0)
        # After renewal, normal tick: usage = netin + netout
        self.assertEqual(svc.bw_usage, 1000)

    @patch('inveterate.tasks.ProxmoxAPI')
    def test_skip_no_renewal_dtm(self, mock_cls):
        """Services with bw_renewal_dtm=None should be skipped."""
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        svc = _service(user, node, sp, bw_renewal_dtm=None)

        from .tasks import meter_bandwidth
        meter_bandwidth()

        svc.refresh_from_db()
        # Should remain unchanged
        self.assertEqual(svc.bw_usage, 0)
        self.assertEqual(svc.bw_system_tick, 0)


# ===================================================================
# TestServiceViewSet
# ===================================================================

class TestServiceViewSet(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.user = _user()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.disk = _disk(self.node)
        self.client = APIClient()

    def test_bulk_import_creates_service_with_plan_name(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post('/api/services/bulk_import/', {
            'default_owner_id': self.admin.id,
            'vms': [{
                'node_id': self.node.id,
                'vmid': 999,
                'name': 'imported-vm',
                'type': 'lxc',
                'status': 'running',
                'maxmem': 1024 * 1024 * 1024,
                'cpus': 2,
                'maxdisk': 20 * 1024 ** 3,
            }]
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        svc = Service.objects.get(machine_id=999)
        self.assertIn('Imported', svc.service_plan.name)

    @patch('inveterate.viewsets.service.ProxmoxAPI')
    def test_console_returns_credentials(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(f'/api/services/{svc.id}/console/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('username', resp.data)
        self.assertIn('password', resp.data)
        self.assertIn('node', resp.data)

    @patch('inveterate.viewsets.service.start_vm')
    def test_start_action_returns_task_id(self, mock_start):
        mock_start.delay.return_value = MagicMock(id='abc-123')
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f'/api/services/{svc.id}/start/')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['task_id'], 'abc-123')

    @patch('inveterate.viewsets.service.stop_vm')
    def test_stop_action_returns_task_id(self, mock_stop):
        mock_stop.delay.return_value = MagicMock(id='def-456')
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f'/api/services/{svc.id}/stop/')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['task_id'], 'def-456')

    def test_non_staff_only_sees_own_services(self):
        sp1 = _service_plan(type='lxc')
        sp2 = _service_plan(type='lxc')
        _service(self.admin, self.node, sp1, hostname='admin.example.com')
        _service(self.user, self.node, sp2, hostname='user.example.com')

        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/services/')
        self.assertEqual(resp.status_code, 200)
        hostnames = [s['hostname'] for s in resp.data['results']]
        self.assertIn('user.example.com', hostnames)
        self.assertNotIn('admin.example.com', hostnames)


# ===================================================================
# TestNodeDiskViewSet
# ===================================================================

class TestNodeDiskViewSet(TestCase):

    def test_bulk_import_shared_disk(self):
        admin = _admin()
        cluster = _cluster()
        node1 = _node(cluster=cluster, name='pve1')
        node2 = _node(cluster=cluster, name='pve2')

        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.post('/api/nodedisks/bulk_import/', {
            'disks': [{
                'storage_name': 'ceph-pool',
                'storage_type': 'rbd',
                'total': 500 * 1024 ** 3,
                'shared': True,
                'shared_nodes': [
                    {'id': node1.id, 'name': node1.name},
                    {'id': node2.id, 'name': node2.name},
                ],
            }]
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        # Both disks should be marked shared
        for nd in NodeDisk.objects.filter(name__startswith='ceph-pool'):
            self.assertTrue(nd.shared)
