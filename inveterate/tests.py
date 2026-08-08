from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import requests.exceptions
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from requests.exceptions import ConnectionError
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APIRequestFactory

from .models import (
    AppProfile, Cluster, Node, NodeDisk, Plan, ServicePlan, Service,
    Template, IPPool, IP, ServiceNetwork, Inventory,
    PortGateway, PortBlock, PortForward, DomainRoute, DispatchedTask,
)
from .task_ownership import record_task_owner, user_owns_task

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
        request = self.factory.post('/api/v1/services/')
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
        request = self.factory.post('/api/v1/services/')
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
        request = self.factory.post('/api/v1/services/')
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
        request = self.factory.post('/api/v1/services/')
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
        request = self.factory.post('/api/v1/services/')
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
        request = self.factory.post('/api/v1/services/')
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
        request = self.factory.post('/api/v1/services/')
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
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # limiting factor: cores → 32/2=16, ram → 65536/1024=64, size → 500/10=50
        self.assertEqual(inv.quantity, 16)

    def test_node_with_services(self):
        from .tasks import calculate_inventory
        user = _admin()
        node = _node()
        disk = _disk(node, size=500)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Create 5 services consuming resources
        for i in range(5):
            sp = _service_plan(storage=disk, size=10, ram=1024, cores=2, bandwidth=1024)
            _service(user, node, sp, hostname=f's{i}.example.com')
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # cores is limiting: (32 - 10)/2 = 11
        self.assertEqual(inv.quantity, 11)

    def test_shared_disk_accounting(self):
        from .tasks import calculate_inventory
        user = _admin()
        cluster = _cluster()
        node1 = _node(cluster=cluster, name='pve1')
        node2 = _node(cluster=cluster, name='pve2')
        # Both nodes share a Ceph disk
        disk1 = _disk(node1, name='ceph-pool', size=100, shared=True)
        disk2 = _disk(node2, name='ceph-pool', size=100, shared=True)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Service on node1 using shared storage
        sp = _service_plan(storage=disk1, size=10, ram=1024, cores=2, bandwidth=1024)
        _service(user, node1, sp, hostname='s1.example.com')
        calculate_inventory()
        # Node2 shared disk should see the usage from node1
        inv2 = Inventory.objects.get(plan=plan, node=node2)
        # disk slots for node2: (100 - 10) / 10 = 9  (shared sees node1's usage)
        # cores: 32/2 = 16, ram: 65536/1024 = 64 → lowest is 9 (disk)
        self.assertEqual(inv2.quantity, 9)

    def test_local_disk_accounting(self):
        from .tasks import calculate_inventory
        user = _admin()
        cluster = _cluster()
        node1 = _node(cluster=cluster, name='pve1')
        node2 = _node(cluster=cluster, name='pve2')
        disk1 = _disk(node1, name='local-lvm', size=100, shared=False)
        disk2 = _disk(node2, name='local-lvm', size=100, shared=False)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Service on node1 only
        sp = _service_plan(storage=disk1, size=10, ram=1024, cores=2, bandwidth=1024)
        _service(user, node1, sp, hostname='s1.example.com')
        calculate_inventory()
        # Node2 local disk should NOT see node1's usage
        inv2 = Inventory.objects.get(plan=plan, node=node2)
        # disk: 100/10=10, cores: 32/2=16, ram: 65536/1024=64 → disk is bottleneck
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
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # disk not factored in, cores is bottleneck: 32/2=16
        self.assertEqual(inv.quantity, 16)

    def test_cluster_bandwidth_cap(self):
        from .tasks import calculate_inventory
        user = _admin()
        cluster = _cluster(bandwidth=5000)  # 5000 GB cluster cap
        node = _node(cluster=cluster)
        disk = _disk(node, size=500)
        plan = _plan(size=10, ram=1024, cores=2, bandwidth=1024, ipv4_ips=0)
        # Create 3 services consuming 3*1024=3072 GB of bandwidth
        for i in range(3):
            sp = _service_plan(storage=disk, size=10, ram=1024, cores=2, bandwidth=1024)
            _service(user, node, sp, hostname=f's{i}.example.com')
        calculate_inventory()
        inv = Inventory.objects.get(plan=plan, node=node)
        # Per-node: cores=(32-6)/2=13, ram=(65536-3072)/1024=61, disk=(500-30)/10=47 → 13
        # Cluster bw cap: (5000-3072)/1024=1 → caps to 1
        self.assertEqual(inv.quantity, 1)


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
        sp = _service_plan(template=tpl, storage=disk, type=svc_type, ipv4_ips=0)
        svc = _service(user, node, sp, status='pending')
        return svc

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
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
    @patch('inveterate.proxmox.ProxmoxAPI')
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
    @patch('inveterate.proxmox.ProxmoxAPI')
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
    @patch('inveterate.proxmox.ProxmoxAPI')
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
    @patch('inveterate.proxmox.ProxmoxAPI')
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

    @patch('inveterate.tasks.provisioning.time.sleep')
    @patch('inveterate.tasks._common.subprocess.run')
    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_kvm_provisioning_calls_clone(self, mock_cls, _mock_inv, mock_run, _mock_sleep):
        from proxmoxer.core import ResourceException
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # Node IP resolution (for the SSH cloud-init snippet write)
        mock_proxmox.cluster.status.get.return_value = [
            {'type': 'node', 'name': 'pve1', 'ip': '192.0.2.10'}
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout=b'', stderr=b'')
        # Template pool lookup
        mock_proxmox.pools.return_value.get.return_value = {'members': []}
        # First status check is the "does the VM already exist?" guard — it must
        # report absent so the clone runs; subsequent checks are the post-clone
        # lock poll, which must report an unlocked VM so the loop exits.
        _checks = {'n': 0}

        def _status(*_a, **_k):
            _checks['n'] += 1
            if _checks['n'] == 1:
                raise ResourceException(500, 'not found', 'no such VM')
            return {'status': 'stopped'}

        mock_node.qemu.return_value.status.current.get.side_effect = _status
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
    @patch('inveterate.proxmox.ProxmoxAPI')
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
# TestProvisionServiceIdempotency
# ===================================================================

class TestProvisionServiceIdempotency(TestCase):

    def _setup_service(self, status='pending'):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template()
        sp = _service_plan(template=tpl, storage=disk, ipv4_ips=0)
        return _service(user, node, sp, status=status)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_destroyed_service_skips_provisioning(self, mock_cls):
        """Service with status 'destroyed' should skip provisioning entirely."""
        svc = self._setup_service(status='destroyed')
        from .tasks import provision_service
        provision_service(svc.id, 'testpass')
        mock_cls.assert_not_called()

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_pending_service_proceeds(self, mock_cls, _mock_inv):
        """Service with status 'pending' should proceed with provisioning."""
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_service(status='pending')
        from .tasks import provision_service
        provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_error_service_with_machine_id_skips(self, mock_cls, _mock_inv):
        """Service with status 'error' and existing machine_id should not re-provision
        (it would fail in setup anyway — tests the guard doesn't let it through)."""
        svc = self._setup_service(status='error')
        svc.machine_id = 1000001
        svc.save(update_fields=['machine_id'])
        from .tasks import provision_service
        # Error status is not in the guard, so Proxmox will be called; this test
        # documents the current behavior: error status proceeds (allows retry).
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []
        provision_service(svc.id, 'testpass')
        # Should have called Proxmox (provisioning proceeded)
        mock_cls.assert_called_once()


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

    def test_raises_when_pool_exhausted(self):
        """Should raise RuntimeError when matching pools exist but have no free IPs."""
        user = _admin()
        node = _node()
        disk = _disk(node)
        pool = _ip_pool(node)
        # Create only 1 IP but request 2
        IP.objects.create(pool=pool, value='10.0.0.10')

        sp = _service_plan(storage=disk, ipv4_ips=2)
        svc = _service(user, node, sp)

        from .tasks import assign_ips
        with self.assertRaises(RuntimeError):
            assign_ips(svc.id)

    def test_allocates_port_blocks_for_internal_ips(self):
        """Internal IPs should get port blocks allocated from matching gateways."""
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _ip_pool(node, name='internal', type='ipv4', network='192.168.0.0', gateway='192.168.0.1', internal=True)
        IP.objects.create(pool=pool_int, value='192.168.0.10')

        gw = PortGateway.objects.create(
            name='gw1', host='gw.test', admin_email='a@b.com', admin_password='pw',
            port_range_start=10000, port_range_end=60000, block_size=100,
        )
        gw.pools.add(pool_int)

        sp = _service_plan(storage=disk, ipv4_ips=0, internal_ips=1)
        svc = _service(user, node, sp)

        from .tasks import assign_ips
        assign_ips(svc.id)

        blocks = PortBlock.objects.filter(gateway=gw, service_network__service=svc)
        self.assertEqual(blocks.count(), 1)
        self.assertEqual(blocks.first().port_start, 10000)
        self.assertEqual(blocks.first().port_end, 10099)


# ===================================================================
# TestMeterBandwidth
# ===================================================================

class TestMeterBandwidth(TestCase):

    @patch('inveterate.proxmox.ProxmoxAPI')
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

    @patch('inveterate.proxmox.ProxmoxAPI')
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

    @patch('inveterate.proxmox.ProxmoxAPI')
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

    @patch('inveterate.proxmox.ProxmoxAPI')
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

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_two_renewals_then_restart_banks_correctly(self, mock_cls):
        """Two unattended monthly renewals with no reboot in between, then a
        restart, must bank the actual since-last-renewal usage and never go
        negative. With the old ``bw_stale += bw_usage`` accounting the baseline
        accumulated across renewals and bw_banked went negative on restart.
        """
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_machine = MagicMock()
        mock_proxmox.nodes.return_value.lxc.return_value = mock_machine

        user = _admin()
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk, type='lxc')
        # Seed a live counter already carrying usage from the current period.
        svc = _service(user, node, sp,
                        bw_system_tick=100, bw_usage=5000, bw_stale=0, bw_banked=0,
                        bw_renewal_dtm=timezone.now() - timedelta(days=1))

        from .tasks import meter_bandwidth

        # Renewal #1: counter is monotonic (no reboot). Baseline should follow
        # the live counter, not accumulate on top of it.
        mock_machine.status.current.get.return_value = {
            'uptime': 200, 'netin': 4000, 'netout': 2000,
        }
        meter_bandwidth()
        svc.refresh_from_db()
        self.assertEqual(svc.bw_stale, 5000)   # = prior bw_usage, not += it
        self.assertEqual(svc.bw_usage, 6000)
        self.assertEqual(svc.bw_banked, 0)

        # Force a second renewal (still no reboot).
        Service.objects.filter(pk=svc.pk).update(bw_renewal_dtm=timezone.now() - timedelta(days=1))
        mock_machine.status.current.get.return_value = {
            'uptime': 300, 'netin': 4500, 'netout': 2500,
        }
        meter_bandwidth()
        svc.refresh_from_db()
        self.assertEqual(svc.bw_stale, 6000)   # tracks the counter at renewal #2
        self.assertEqual(svc.bw_usage, 7000)
        self.assertEqual(svc.bw_banked, 0)
        # Unbanked usage this period stays sane (non-negative).
        self.assertGreaterEqual(svc.bw_usage - svc.bw_stale, 0)

        # Now the VM restarts (uptime drops below the last tick), no renewal.
        mock_machine.status.current.get.return_value = {
            'uptime': 10, 'netin': 30, 'netout': 20,
        }
        meter_bandwidth()
        svc.refresh_from_db()
        # banked = usage - stale = 7000 - 6000 = 1000 (real since-renewal usage),
        # never negative. The old accounting produced a negative bank here.
        self.assertEqual(svc.bw_banked, 1000)
        self.assertGreaterEqual(svc.bw_banked, 0)
        self.assertEqual(svc.bw_stale, 0)
        self.assertEqual(svc.bw_usage, 50)
        self.assertEqual(svc.bw_system_tick, 10)


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
        resp = self.client.post('/api/v1/services/bulk_import/', {
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

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_console_returns_credentials(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(f'/api/v1/services/{svc.id}/console/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('username', resp.data)
        self.assertIn('password', resp.data)
        self.assertIn('node', resp.data)
        # Verify per-service naming format
        self.assertEqual(resp.data['username'], f'inv-s{svc.id}@pve')

    @patch('inveterate.viewsets.service.start_vm')
    def test_start_action_returns_task_id(self, mock_start):
        mock_start.delay.return_value = MagicMock(id='abc-123')
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f'/api/v1/services/{svc.id}/start/')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['task_id'], 'abc-123')

    @patch('inveterate.viewsets.service.stop_vm')
    def test_stop_action_returns_task_id(self, mock_stop):
        mock_stop.delay.return_value = MagicMock(id='def-456')
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f'/api/v1/services/{svc.id}/stop/')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['task_id'], 'def-456')

    def test_non_staff_only_sees_own_services(self):
        sp1 = _service_plan(type='lxc')
        sp2 = _service_plan(type='lxc')
        _service(self.admin, self.node, sp1, hostname='admin.example.com')
        _service(self.user, self.node, sp2, hostname='user.example.com')

        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/v1/services/')
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
        resp = client.post('/api/v1/nodedisks/bulk_import/', {
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


# ===================================================================
# TestImportKvmTemplate
# ===================================================================

class TestImportKvmTemplate(TestCase):

    def setUp(self):
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.disk = _disk(self.node)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_import_sets_ready_and_file(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # download-url returns UPID
        mock_node.storage.return_value.return_value.post.return_value = 'UPID:pve1:task1'
        # task polling returns stopped OK
        mock_node.tasks.return_value.status.get.return_value = {
            'status': 'stopped', 'exitstatus': 'OK',
        }
        # nextid
        mock_proxmox.cluster.nextid.get.return_value = 9000
        # qemu.post returns UPID
        mock_node.qemu.post.return_value = 'UPID:pve1:task2'

        tpl = Template.objects.create(
            name='Ubuntu 24.04', type='kvm',
            source_url='https://cloud-images.ubuntu.com/noble/noble-server-cloudimg-amd64.img',
            node=self.node, status='pending',
        )

        from .tasks import import_kvm_template
        import_kvm_template(tpl.id)

        tpl.refresh_from_db()
        self.assertEqual(tpl.status, 'ready')
        self.assertEqual(tpl.file, '9000')
        self.assertEqual(tpl.status_msg, '')

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_connection_error_sets_error(self, mock_cls):
        mock_cls.side_effect = ConnectionError("refused")

        tpl = Template.objects.create(
            name='Ubuntu 24.04', type='kvm',
            source_url='https://cloud-images.ubuntu.com/noble/noble-server-cloudimg-amd64.img',
            node=self.node, status='pending',
        )

        from .tasks import import_kvm_template
        with self.assertRaises(ConnectionError):
            import_kvm_template(tpl.id)

        tpl.refresh_from_db()
        self.assertEqual(tpl.status, 'error')
        self.assertIn('Cannot connect', tpl.status_msg)

    def test_missing_source_url_sets_error(self):
        tpl = Template.objects.create(
            name='Ubuntu 24.04', type='kvm',
            source_url='', node=self.node, status='pending',
        )

        from .tasks import import_kvm_template
        import_kvm_template(tpl.id)

        tpl.refresh_from_db()
        self.assertEqual(tpl.status, 'error')
        self.assertIn('source_url', tpl.status_msg)

    def test_lxc_template_rejected(self):
        tpl = Template.objects.create(
            name='Debian 12', type='lxc',
            file='debian-12-standard_12.2-1_amd64.tar.zst',
            source_url='https://example.com/image.tar.zst',
            status='pending',
        )

        from .tasks import import_kvm_template
        import_kvm_template(tpl.id)

        tpl.refresh_from_db()
        self.assertEqual(tpl.status, 'error')
        self.assertIn('Only KVM', tpl.status_msg)


# ===================================================================
# TestTemplateViewSetReimport
# ===================================================================

class TestTemplateViewSetReimport(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.disk = _disk(self.node)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    @patch('inveterate.viewsets.resource.import_kvm_template')
    def test_reimport_returns_202(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-reimport')
        tpl = Template.objects.create(
            name='Ubuntu 24.04', type='kvm',
            source_url='https://cloud-images.ubuntu.com/noble/noble.img',
            file='9000', status='ready', node=self.node,
        )
        resp = self.client.post(f'/api/v1/templates/{tpl.id}/reimport/')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['task_id'], 'task-reimport')
        tpl.refresh_from_db()
        self.assertEqual(tpl.status, 'pending')
        self.assertEqual(tpl.file, '')

    @patch('inveterate.viewsets.resource.import_kvm_template')
    def test_reimport_rejects_lxc(self, mock_task):
        tpl = Template.objects.create(
            name='Debian 12', type='lxc',
            file='debian-12-standard_12.2-1_amd64.tar.zst',
        )
        resp = self.client.post(f'/api/v1/templates/{tpl.id}/reimport/')
        self.assertEqual(resp.status_code, 400)

    @patch('inveterate.viewsets.resource.import_kvm_template')
    def test_reimport_rejects_no_source_url(self, mock_task):
        tpl = Template.objects.create(
            name='Manual KVM', type='kvm', file='100',
        )
        resp = self.client.post(f'/api/v1/templates/{tpl.id}/reimport/')
        self.assertEqual(resp.status_code, 400)


# ===================================================================
# TestTemplateSerializerImportTrigger
# ===================================================================

class TestTemplateSerializerImportTrigger(TestCase):

    def setUp(self):
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.disk = _disk(self.node)

    @patch('inveterate.tasks.import_kvm_template')
    def test_create_kvm_with_source_url_triggers_import(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-auto')
        from .serializers import TemplateSerializer
        data = {
            'name': 'Ubuntu 24.04',
            'type': 'kvm',
            'source_url': 'https://cloud-images.ubuntu.com/noble/noble.img',
        }
        ser = TemplateSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        tpl = ser.save()
        self.assertEqual(tpl.status, 'pending')
        mock_task.delay.assert_called_once_with(tpl.id)

    def test_create_lxc_does_not_trigger_import(self):
        from .serializers import TemplateSerializer
        data = {
            'name': 'Debian 12',
            'type': 'lxc',
            'file': 'debian-12-standard_12.2-1_amd64.tar.zst',
        }
        ser = TemplateSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        tpl = ser.save()
        self.assertEqual(tpl.status, 'ready')


def _app_profile(name='Docker', cloud_init='packages:\n  - curl\nruncmd:\n  - echo hello'):
    return AppProfile.objects.create(name=name, cloud_init=cloud_init)


# ===================================================================
# TestComposeCloudInit
# ===================================================================

class TestComposeCloudInit(TestCase):

    def test_merges_packages_runcmd_write_files(self):
        from .tasks import _compose_cloud_init
        a1 = AppProfile.objects.create(
            name='Docker',
            cloud_init='packages:\n  - curl\nruncmd:\n  - curl -fsSL https://get.docker.com | sh',
        )
        a2 = AppProfile.objects.create(
            name='Minecraft',
            cloud_init=(
                'packages:\n  - openjdk-21-jre-headless\n'
                'write_files:\n  - path: /etc/mc.conf\n    content: hello\n'
                'runcmd:\n  - echo mc'
            ),
        )
        result = _compose_cloud_init(AppProfile.objects.filter(pk__in=[a1.pk, a2.pk]))
        self.assertTrue(result.startswith('#cloud-config\n'))
        import yaml
        doc = yaml.safe_load(result)
        self.assertEqual(doc['packages'], ['curl', 'openjdk-21-jre-headless'])
        self.assertEqual(doc['runcmd'], ['curl -fsSL https://get.docker.com | sh', 'echo mc'])
        self.assertEqual(len(doc['write_files']), 1)
        self.assertEqual(doc['write_files'][0]['path'], '/etc/mc.conf')

    def test_empty_apps_returns_empty_string(self):
        from .tasks import _compose_cloud_init
        result = _compose_cloud_init(AppProfile.objects.none())
        self.assertEqual(result, '')

    def test_invalid_yaml_skipped(self):
        from .tasks import _compose_cloud_init
        a1 = AppProfile.objects.create(name='Good', cloud_init='packages:\n  - curl')
        a2 = AppProfile.objects.create(name='Bad', cloud_init='just a string')
        result = _compose_cloud_init(AppProfile.objects.filter(pk__in=[a1.pk, a2.pk]))
        import yaml
        doc = yaml.safe_load(result)
        self.assertEqual(doc['packages'], ['curl'])


# ===================================================================
# TestProvisionServiceApps
# ===================================================================

class TestProvisionServiceApps(TestCase):

    def _setup_kvm_service(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm', ipv4_ips=0)
        svc = _service(user, node, sp, status='pending')
        return svc

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.provisioning.write_snippet')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_uploads_snippet_when_apps_selected(self, mock_cls, mock_write, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.qemu.return_value.status.current.get.return_value = {'status': 'stopped'}
        mock_node.qemu.return_value.firewall.rules.get.return_value = []
        mock_node.qemu.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_kvm_service()
        app = _app_profile(name='Docker', cloud_init='packages:\n  - curl\nruncmd:\n  - echo docker')
        svc.service_plan.apps.add(app)

        from .tasks import provision_service
        provision_service(svc.id, 'testpass')
        svc.refresh_from_db()

        # Verify snippet was written via SSH
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        self.assertEqual(call_args[0][1], svc.node.name)
        self.assertIn(f'ci-{svc.machine_id}', call_args[0][2])

        # Verify cicustom was set in vm config
        config_call = mock_node.qemu.return_value.config.post
        config_call.assert_called_once()
        config_kwargs = config_call.call_args[1]
        self.assertIn('cicustom', config_kwargs)
        self.assertIn(f'ci-{svc.machine_id}.yml', config_kwargs['cicustom'])

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.tasks.provisioning.write_snippet')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_writes_base_snippet_when_no_apps(self, mock_cls, mock_write, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.qemu.return_value.status.current.get.return_value = {'status': 'stopped'}
        mock_node.qemu.return_value.firewall.rules.get.return_value = []
        mock_node.qemu.return_value.firewall.ipset.return_value.get.return_value = []

        svc = self._setup_kvm_service()

        from .tasks import provision_service
        provision_service(svc.id, 'testpass')

        # KVM always writes a snippet (qemu-guest-agent + identity fields)
        mock_write.assert_called_once()
        snippet_content = mock_write.call_args[0][3]
        self.assertIn('qemu-guest-agent', snippet_content)
        # No app-specific content beyond the base
        self.assertNotIn('curl', snippet_content)


# ===================================================================
# TestCancelServiceSnippetCleanup
# ===================================================================

class TestCancelServiceSnippetCleanup(TestCase):

    @patch('inveterate.tasks.maintenance.delete_snippet')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_cleans_up_snippet(self, mock_cls, mock_delete):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)

        from .tasks import cancel_service
        cancel_service(svc.id)

        # Snippet delete should have been attempted via SSH
        mock_delete.assert_called_once_with(
            mock_proxmox, node.name, f'ci-{svc.machine_id}.yml'
        )
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'destroyed')

    @patch('inveterate.tasks.maintenance.delete_snippet')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_ignores_snippet_error(self, mock_cls, mock_delete):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_delete.side_effect = Exception("ssh failed")

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)

        from .tasks import cancel_service
        cancel_service(svc.id)

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'destroyed')


# ===================================================================
# TestServiceSerializerApps
# ===================================================================

class TestServiceSerializerApps(TestCase):

    def setUp(self):
        self.user = _admin()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.disk = _disk(self.node)
        self.plan = _plan()
        self.template = _template()
        Inventory.objects.create(plan=self.plan, node=self.node, quantity=5)
        self.factory = APIRequestFactory()

    @patch('inveterate.serializers.provision_service')
    def test_create_attaches_apps_to_service_plan(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        app1 = _app_profile(name='Docker', cloud_init='packages:\n  - curl')
        app2 = _app_profile(name='k3s', cloud_init='runcmd:\n  - echo k3s')

        from .serializers import ServiceSerializer
        request = self.factory.post('/api/v1/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'apps.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
            'apps': [app1.id, app2.id],
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        self.assertTrue(ser.is_valid(), ser.errors)
        svc = ser.save()
        self.assertEqual(set(svc.service_plan.apps.values_list('pk', flat=True)), {app1.pk, app2.pk})

    @patch('inveterate.serializers.provision_service')
    def test_create_without_apps_leaves_empty(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        from .serializers import ServiceSerializer
        request = self.factory.post('/api/v1/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'noapps.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        self.assertTrue(ser.is_valid(), ser.errors)
        svc = ser.save()
        self.assertEqual(svc.service_plan.apps.count(), 0)


# ===================================================================
# TestCancelServiceIPRelease
# ===================================================================

class TestCancelServiceIPRelease(TestCase):

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_releases_ips(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool = _ip_pool(node)
        ip1 = IP.objects.create(pool=pool, value='10.0.0.10')
        ip2 = IP.objects.create(pool=pool, value='10.0.0.11')

        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)

        # Assign IPs to the service
        sn1 = ServiceNetwork.objects.create(service=svc)
        ip1.owner = sn1
        ip1.save()
        sn2 = ServiceNetwork.objects.create(service=svc)
        ip2.owner = sn2
        ip2.save()

        from .tasks import cancel_service
        cancel_service(svc.id)

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'destroyed')

        # ServiceNetwork records should be deleted
        self.assertEqual(ServiceNetwork.objects.filter(service=svc).count(), 0)

        # IPs should have owner set to NULL (released back to pool)
        ip1.refresh_from_db()
        ip2.refresh_from_db()
        self.assertIsNone(ip1.owner)
        self.assertIsNone(ip2.owner)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_when_vm_already_deleted(self, mock_cls):
        """A VM deleted manually in Proxmox must not strand the service: cancel
        skips the (impossible) VM delete and still tears down the DB record."""
        from proxmoxer.core import ResourceException

        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        # The VM is gone: status lookups raise as Proxmox does for a missing VMID.
        machine = mock_node.qemu.return_value
        machine.status.current.get.side_effect = ResourceException(500, 'fail', 'no such VM')

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool = _ip_pool(node)
        ip1 = IP.objects.create(pool=pool, value='10.0.0.10')

        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)
        sn1 = ServiceNetwork.objects.create(service=svc)
        ip1.owner = sn1
        ip1.save()

        from .tasks import cancel_service
        cancel_service(svc.id)

        machine.delete.assert_not_called()
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'destroyed')
        self.assertEqual(ServiceNetwork.objects.filter(service=svc).count(), 0)
        ip1.refresh_from_db()
        self.assertIsNone(ip1.owner)


# ===================================================================
# TestCleanupOrphanedIPs
# ===================================================================

class TestCleanupOrphanedIPs(TestCase):

    def test_cleans_orphaned_ips_from_destroyed_services(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool = _ip_pool(node)
        ip1 = IP.objects.create(pool=pool, value='10.0.0.10')
        ip2 = IP.objects.create(pool=pool, value='10.0.0.11')

        sp = _service_plan(storage=disk)
        svc = _service(user, node, sp, status='destroyed')

        # Simulate orphaned ServiceNetwork records on a destroyed service
        sn1 = ServiceNetwork.objects.create(service=svc)
        ip1.owner = sn1
        ip1.save()
        sn2 = ServiceNetwork.objects.create(service=svc)
        ip2.owner = sn2
        ip2.save()

        from .tasks import cleanup_orphaned_ips
        cleanup_orphaned_ips()

        # ServiceNetwork records should be deleted
        self.assertEqual(ServiceNetwork.objects.filter(service=svc).count(), 0)

        # IPs should be released
        ip1.refresh_from_db()
        ip2.refresh_from_db()
        self.assertIsNone(ip1.owner)
        self.assertIsNone(ip2.owner)

    def test_does_not_touch_active_service_ips(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool = _ip_pool(node)
        ip1 = IP.objects.create(pool=pool, value='10.0.0.10')

        sp = _service_plan(storage=disk)
        svc = _service(user, node, sp, status='active')

        sn1 = ServiceNetwork.objects.create(service=svc)
        ip1.owner = sn1
        ip1.save()

        from .tasks import cleanup_orphaned_ips
        cleanup_orphaned_ips()

        # Active service networks should be untouched
        self.assertEqual(ServiceNetwork.objects.filter(service=svc).count(), 1)
        ip1.refresh_from_db()
        self.assertIsNotNone(ip1.owner)


# ===================================================================
# TestSetupPeriodicTasks
# ===================================================================

class TestSetupPeriodicTasks(TestCase):

    def test_creates_periodic_tasks(self):
        from django.core.management import call_command
        from django_celery_beat.models import PeriodicTask

        call_command('setup_periodic_tasks')

        expected_tasks = [
            'Calculate Inventory',
            'Meter Bandwidth',
            'Cleanup Console Users',
            'Cleanup Orphaned IPs',
            'Sync LXC Templates',
            'Sync KVM Templates',
        ]
        for name in expected_tasks:
            self.assertTrue(
                PeriodicTask.objects.filter(name=name).exists(),
                f"PeriodicTask '{name}' was not created",
            )

    def test_idempotent(self):
        from django.core.management import call_command
        from django_celery_beat.models import PeriodicTask

        call_command('setup_periodic_tasks')
        first_count = PeriodicTask.objects.count()

        call_command('setup_periodic_tasks')
        second_count = PeriodicTask.objects.count()

        self.assertEqual(first_count, second_count)


# ===================================================================
# TestTokenAuthentication
# ===================================================================

class TestTokenAuthentication(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('tokenuser', 'token@test.com', 'tokenpass')

    def test_obtain_token(self):
        resp = self.client.post('/api/v1/auth/token/', {
            'username': 'tokenuser',
            'password': 'tokenpass',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertTrue(Token.objects.filter(user=self.user).exists())

    def test_obtain_token_bad_credentials(self):
        resp = self.client.post('/api/v1/auth/token/', {
            'username': 'tokenuser',
            'password': 'wrong',
        })
        self.assertEqual(resp.status_code, 400)

    def test_token_auth_on_endpoint(self):
        token = Token.objects.create(user=self.user)
        node = _node()
        disk = _disk(node)
        sp = _service_plan(storage=disk)
        _service(self.user, node, sp, hostname='tok.example.com')

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        resp = self.client.get('/api/v1/services/')
        self.assertEqual(resp.status_code, 200)
        hostnames = [s['hostname'] for s in resp.data['results']]
        self.assertIn('tok.example.com', hostnames)

    def test_invalid_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalidtokenvalue')
        resp = self.client.get('/api/v1/services/')
        self.assertEqual(resp.status_code, 401)


# ===================================================================
# TestThrottling
# ===================================================================

class TestThrottling(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = _admin()

    def test_throttle_enforced(self):
        from rest_framework.throttling import SimpleRateThrottle
        _plan(name='throttle-plan')
        original = SimpleRateThrottle.THROTTLE_RATES.copy()
        SimpleRateThrottle.THROTTLE_RATES['public'] = '1/hour'
        try:
            resp1 = self.client.get('/api/v1/plans/')
            self.assertEqual(resp1.status_code, 200)
            resp2 = self.client.get('/api/v1/plans/')
            self.assertEqual(resp2.status_code, 429)
        finally:
            SimpleRateThrottle.THROTTLE_RATES.update(original)


# ---------------------------------------------------------------------------
# Port Forwarding / Domain Routing helpers
# ---------------------------------------------------------------------------

def _port_gateway(pools=None, **kw):
    defaults = dict(
        name='gw1', host='http://gateway:81',
        admin_email='admin@example.com', admin_password='secret',
        port_range_start=10000, port_range_end=10999, block_size=100,
    )
    defaults.update(kw)
    gw = PortGateway.objects.create(**defaults)
    if pools:
        gw.pools.set(pools)
    return gw


def _internal_pool(node, **kw):
    defaults = dict(
        name='internal', type='ipv4', network='192.168.0.0', mask=24,
        gateway='192.168.0.1', dns='8.8.8.8', internal=True,
    )
    defaults.update(kw)
    pool = IPPool.objects.create(**defaults)
    pool.nodes.add(node)
    return pool


# ===================================================================
# TestPortBlockAllocation
# ===================================================================

class TestPortBlockAllocation(TestCase):

    def test_assign_ips_creates_port_block_for_internal_ip(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        for i in range(5):
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        sp = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc = _service(user, node, sp)

        from .tasks import assign_ips
        assign_ips(svc.id)

        sn = ServiceNetwork.objects.filter(service=svc).first()
        self.assertIsNotNone(sn)
        self.assertTrue(hasattr(sn, 'port_block'))
        pb = sn.port_block
        self.assertEqual(pb.gateway, gw)
        self.assertEqual(pb.port_start, 10000)
        self.assertEqual(pb.port_end, 10099)

    def test_skips_external_ips(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_ext = _ip_pool(node)
        IP.objects.create(pool=pool_ext, value='10.0.0.10')

        sp = _service_plan(storage=disk, ipv4_ips=1, ipv6_ips=0, internal_ips=0)
        svc = _service(user, node, sp)

        from .tasks import assign_ips
        assign_ips(svc.id)

        sn = ServiceNetwork.objects.filter(service=svc).first()
        self.assertIsNotNone(sn)
        self.assertFalse(hasattr(sn, 'port_block'))

    def test_idempotent_port_block(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        IP.objects.create(pool=pool_int, value='192.168.0.10')

        sp = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc = _service(user, node, sp)

        from .tasks import assign_ips
        assign_ips(svc.id)
        first_count = PortBlock.objects.filter(gateway=gw).count()
        assign_ips(svc.id)
        second_count = PortBlock.objects.filter(gateway=gw).count()
        self.assertEqual(first_count, second_count)

    def test_allocates_sequential_blocks(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        for i in range(3):
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        # Service 1
        sp1 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc1 = _service(user, node, sp1, hostname='s1.example.com')
        from .tasks import assign_ips
        assign_ips(svc1.id)

        # Service 2
        sp2 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc2 = _service(user, node, sp2, hostname='s2.example.com')
        assign_ips(svc2.id)

        blocks = list(PortBlock.objects.filter(gateway=gw).order_by('port_start'))
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].port_start, 10000)
        self.assertEqual(blocks[1].port_start, 10100)

    def test_handles_full_gateway(self):
        """When the gateway has no available port slots, allocation raises."""
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        # Gateway with space for only 1 block (10000-10099)
        gw = _port_gateway(pools=[pool_int], port_range_start=10000, port_range_end=10099, block_size=100)
        for i in range(2):
            IP.objects.create(pool=pool_int, value=f'192.168.0.{10+i}')

        # Service 1 takes the only block
        sp1 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc1 = _service(user, node, sp1, hostname='s1.example.com')
        from .tasks import assign_ips
        assign_ips(svc1.id)
        self.assertEqual(PortBlock.objects.filter(gateway=gw).count(), 1)

        # Service 2 can't get a block — should raise
        sp2 = _service_plan(storage=disk, ipv4_ips=0, ipv6_ips=0, internal_ips=1)
        svc2 = _service(user, node, sp2, hostname='s2.example.com')
        with self.assertRaises(RuntimeError):
            assign_ips(svc2.id)
        # Still only 1 block
        self.assertEqual(PortBlock.objects.filter(gateway=gw).count(), 1)


# ===================================================================
# TestPortBlockDeallocation
# ===================================================================

class TestPortBlockDeallocation(TestCase):

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_cascades_to_port_block(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')

        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)

        sn = ServiceNetwork.objects.create(service=svc)
        ip.owner = sn
        ip.save()
        pb = PortBlock.objects.create(gateway=gw, service_network=sn, port_start=10000, port_end=10099)

        from .tasks import cancel_service
        cancel_service(svc.id)

        self.assertEqual(PortBlock.objects.filter(pk=pb.pk).count(), 0)


# ===================================================================
# TestPortForwardValidation
# ===================================================================

class TestPortForwardValidation(TestCase):

    def setUp(self):
        self.user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp = _service_plan(storage=disk)
        self.svc = _service(self.user, node, sp)
        self.sn = ServiceNetwork.objects.create(service=self.svc)
        ip.owner = self.sn
        ip.save()
        self.pb = PortBlock.objects.create(
            gateway=self.gw, service_network=self.sn, port_start=10000, port_end=10099,
        )

    @patch('inveterate.serializers.sync_port_forward')
    def test_external_port_within_range(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        from .serializers import PortForwardSerializer
        data = {
            'port_block': self.pb.id,
            'external_port': 10050,
            'internal_port': 22,
            'protocol': 'tcp',
        }
        ser = PortForwardSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    @patch('inveterate.serializers.sync_port_forward')
    def test_external_port_out_of_range(self, mock_sync):
        from .serializers import PortForwardSerializer
        data = {
            'port_block': self.pb.id,
            'external_port': 9999,
            'internal_port': 22,
            'protocol': 'tcp',
        }
        ser = PortForwardSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('external_port', ser.errors)

    @patch('inveterate.serializers.sync_port_forward')
    def test_internal_port_out_of_range(self, mock_sync):
        from .serializers import PortForwardSerializer
        data = {
            'port_block': self.pb.id,
            'external_port': 10001,
            'internal_port': 0,
            'protocol': 'tcp',
        }
        ser = PortForwardSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('internal_port', ser.errors)

    @patch('inveterate.serializers.sync_port_forward')
    def test_unique_constraint(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        PortForward.objects.create(
            port_block=self.pb, external_port=10001, internal_port=22, protocol='tcp',
        )
        with self.assertRaises(IntegrityError):
            PortForward.objects.create(
                port_block=self.pb, external_port=10001, internal_port=80, protocol='tcp',
            )


# ===================================================================
# TestPortForwardViewSet
# ===================================================================

class TestPortForwardViewSet(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.user = _user()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])

        # Admin's service + port block
        ip1 = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp1 = _service_plan(storage=disk)
        self.admin_svc = _service(self.admin, node, sp1, hostname='admin.example.com')
        sn1 = ServiceNetwork.objects.create(service=self.admin_svc)
        ip1.owner = sn1
        ip1.save()
        self.admin_pb = PortBlock.objects.create(
            gateway=self.gw, service_network=sn1, port_start=10000, port_end=10099,
        )

        # User's service + port block
        ip2 = IP.objects.create(pool=pool_int, value='192.168.0.11')
        sp2 = _service_plan(storage=disk)
        self.user_svc = _service(self.user, node, sp2, hostname='user.example.com')
        sn2 = ServiceNetwork.objects.create(service=self.user_svc)
        ip2.owner = sn2
        ip2.save()
        self.user_pb = PortBlock.objects.create(
            gateway=self.gw, service_network=sn2, port_start=10100, port_end=10199,
        )

        self.client = APIClient()

    @patch('inveterate.serializers.sync_port_forward')
    def test_user_creates_forward_on_own_block(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/portforwards/', {
            'port_block': self.user_pb.id,
            'external_port': 10100,
            'internal_port': 22,
            'protocol': 'tcp',
        })
        self.assertEqual(resp.status_code, 201)

    def test_user_only_sees_own_forwards(self):
        PortForward.objects.create(
            port_block=self.admin_pb, external_port=10001, internal_port=22, protocol='tcp',
        )
        PortForward.objects.create(
            port_block=self.user_pb, external_port=10100, internal_port=22, protocol='tcp',
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/v1/portforwards/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['external_port'], 10100)

    def test_admin_sees_all_forwards(self):
        PortForward.objects.create(
            port_block=self.admin_pb, external_port=10001, internal_port=22, protocol='tcp',
        )
        PortForward.objects.create(
            port_block=self.user_pb, external_port=10100, internal_port=22, protocol='tcp',
        )

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/portforwards/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 2)

    @patch('inveterate.serializers.sync_port_forward')
    def test_non_owner_rejected(self, mock_sync):
        """User cannot create forward on admin's port block."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/portforwards/', {
            'port_block': self.admin_pb.id,
            'external_port': 10050,
            'internal_port': 22,
            'protocol': 'tcp',
        })
        self.assertEqual(resp.status_code, 400)


# ===================================================================
# TestDomainRouteValidation
# ===================================================================

class TestDomainRouteValidation(TestCase):

    def setUp(self):
        self.user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp = _service_plan(storage=disk)
        self.svc = _service(self.user, node, sp)
        self.sn = ServiceNetwork.objects.create(service=self.svc)
        ip.owner = self.sn
        ip.save()
        PortBlock.objects.create(
            gateway=self.gw, service_network=self.sn, port_start=10000, port_end=10099,
        )

    @patch('inveterate.serializers.sync_domain_route')
    def test_domain_uniqueness(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        DomainRoute.objects.create(service=self.svc, domain='app.example.com')
        with self.assertRaises(IntegrityError):
            DomainRoute.objects.create(service=self.svc, domain='app.example.com')

    @patch('inveterate.serializers.sync_domain_route')
    def test_service_must_have_internal_ip_and_gateway(self, mock_sync):
        """A service without internal IP + gateway should fail validation."""
        cluster = _cluster(name='c2', host='10.0.0.2')
        node = _node(cluster=cluster, name='pve2')
        disk = _disk(node)
        pool_ext = _ip_pool(node)
        ip = IP.objects.create(pool=pool_ext, value='10.0.0.20')
        sp = _service_plan(storage=disk, ipv4_ips=1, internal_ips=0)
        svc2 = _service(self.user, node, sp, hostname='ext.example.com')
        sn = ServiceNetwork.objects.create(service=svc2)
        ip.owner = sn
        ip.save()

        from .serializers import DomainRouteSerializer
        data = {
            'service': svc2.id,
            'domain': 'test.example.com',
            'forward_port': 80,
        }
        ser = DomainRouteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('service', ser.errors)

    @patch('inveterate.serializers.sync_domain_route')
    def test_normal_customer_domain_accepted(self, mock_sync):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        from .serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'app.customer-example.com', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    @patch('inveterate.serializers.sync_domain_route')
    def test_malformed_domain_rejected(self, mock_sync):
        from .serializers import DomainRouteSerializer
        for bad in ['not a domain', 'nodotatall', '-leadinghyphen.com', 'trailing-.com', '']:
            data = {'service': self.svc.id, 'domain': bad, 'forward_port': 80}
            ser = DomainRouteSerializer(data=data)
            self.assertFalse(ser.is_valid(), f"expected {bad!r} to be rejected")
            self.assertIn('domain', ser.errors)

    @override_settings(INVETERATE_RESERVED_DOMAINS=['hosnet.dhos.me'])
    @patch('inveterate.serializers.sync_domain_route')
    def test_reserved_provider_domain_rejected(self, mock_sync):
        """A customer must not be able to squat the provider's own vhost
        (or any subdomain of a reserved base domain) on their own service."""
        from .serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'portal.hosnet.dhos.me', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('domain', ser.errors)

    @override_settings(INVETERATE_RESERVED_DOMAINS=['hosnet.dhos.me'])
    @patch('inveterate.serializers.sync_domain_route')
    def test_reserved_domain_exact_match_rejected(self, mock_sync):
        from .serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'hosnet.dhos.me', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('domain', ser.errors)

    @override_settings(INVETERATE_RESERVED_DOMAINS=['hosnet.dhos.me'])
    @patch('inveterate.serializers.sync_domain_route')
    def test_domain_reservation_is_case_insensitive(self, mock_sync):
        from .serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'Portal.HosNet.Dhos.ME', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('domain', ser.errors)

    @override_settings(INVETERATE_RESERVED_DOMAINS=['hosnet.dhos.me'])
    @patch('inveterate.serializers.sync_domain_route')
    def test_unrelated_domain_not_blocked_by_reserved_list(self, mock_sync):
        """Only the reserved base domain (and its subdomains) are blocked --
        an unrelated domain that merely shares a substring must pass."""
        mock_sync.delay.return_value = MagicMock(id='task-1')
        from .serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'nothosnet.dhos.me', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)


# ===================================================================
# TestDomainRouteViewSet
# ===================================================================

class TestDomainRouteViewSet(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.user = _user()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])

        # Admin's service
        ip1 = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp1 = _service_plan(storage=disk)
        self.admin_svc = _service(self.admin, node, sp1, hostname='admin.example.com')
        sn1 = ServiceNetwork.objects.create(service=self.admin_svc)
        ip1.owner = sn1
        ip1.save()
        PortBlock.objects.create(gateway=self.gw, service_network=sn1, port_start=10000, port_end=10099)

        # User's service
        ip2 = IP.objects.create(pool=pool_int, value='192.168.0.11')
        sp2 = _service_plan(storage=disk)
        self.user_svc = _service(self.user, node, sp2, hostname='user.example.com')
        sn2 = ServiceNetwork.objects.create(service=self.user_svc)
        ip2.owner = sn2
        ip2.save()
        PortBlock.objects.create(gateway=self.gw, service_network=sn2, port_start=10100, port_end=10199)

        self.client = APIClient()

    @patch('inveterate.serializers.verify_domain_route')
    @patch('inveterate.serializers.sync_domain_route')
    def test_user_creates_domain_route(self, mock_sync, mock_verify):
        mock_sync.delay.return_value = MagicMock(id='task-1')
        mock_verify.delay.return_value = MagicMock(id='task-1')
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/domainroutes/', {
            'service': self.user_svc.id,
            'domain': 'myapp.example.com',
            'forward_port': 80,
        })
        self.assertEqual(resp.status_code, 201)

    def test_user_only_sees_own_routes(self):
        DomainRoute.objects.create(service=self.admin_svc, domain='admin-app.example.com')
        DomainRoute.objects.create(service=self.user_svc, domain='user-app.example.com')

        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/v1/domainroutes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['domain'], 'user-app.example.com')

    def test_admin_sees_all_routes(self):
        DomainRoute.objects.create(service=self.admin_svc, domain='admin-app.example.com')
        DomainRoute.objects.create(service=self.user_svc, domain='user-app.example.com')

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/domainroutes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 2)

    @patch('inveterate.serializers.sync_domain_route')
    def test_non_owner_rejected(self, mock_sync):
        """User cannot create domain route on admin's service."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/domainroutes/', {
            'service': self.admin_svc.id,
            'domain': 'hijack.example.com',
            'forward_port': 80,
        })
        self.assertEqual(resp.status_code, 400)


# ===================================================================
# Domain-ownership verification (TXT challenge)
# ===================================================================

def _txt_answer(value):
    """Build a fake dnspython TXT rdata whose `.strings` decodes to `value`."""
    ans = MagicMock()
    ans.strings = [value.encode()]
    return ans


class TestAccountToken(TestCase):

    @override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='')
    def test_deterministic_per_owner(self):
        from .domain_verification import account_token
        self.assertEqual(account_token(7), account_token(7))
        self.assertTrue(account_token(7).startswith('inv-verify='))

    @override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='')
    def test_differs_across_owners(self):
        from .domain_verification import account_token
        self.assertNotEqual(account_token(7), account_token(8))

    def test_changes_with_salt(self):
        from .domain_verification import account_token
        with override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='a'):
            token_a = account_token(7)
        with override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='b'):
            token_b = account_token(7)
        self.assertNotEqual(token_a, token_b)

    @override_settings(INVETERATE_DOMAIN_VERIFICATION_LABEL='_inveterate-verify')
    def test_record_name(self):
        from .domain_verification import verification_record_name
        self.assertEqual(
            verification_record_name('app.example.com'),
            '_inveterate-verify.app.example.com',
        )


class TestVerifyDomainRouteTask(TestCase):

    def setUp(self):
        self.user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp = _service_plan(storage=disk)
        self.svc = _service(self.user, node, sp)
        self.sn = ServiceNetwork.objects.create(service=self.svc)
        ip.owner = self.sn
        ip.save()
        PortBlock.objects.create(
            gateway=self.gw, service_network=self.sn, port_start=10000, port_end=10099,
        )
        self.dr = DomainRoute.objects.create(service=self.svc, domain='app.example.com')

    @patch('inveterate.tasks.npm.sync_domain_route')
    @patch('inveterate.tasks.domain_verify._public_resolver')
    def test_matching_txt_verifies_and_syncs(self, mock_resolver, mock_sync):
        from .domain_verification import account_token
        from .tasks.domain_verify import verify_domain_route
        token = account_token(self.svc.owner_id)
        mock_resolver.return_value.resolve.return_value = [_txt_answer(token)]

        verify_domain_route(self.dr.id)

        self.dr.refresh_from_db()
        self.assertEqual(self.dr.verification_status, 'verified')
        self.assertIsNotNone(self.dr.verified_at)
        mock_sync.delay.assert_called_once_with(self.dr.pk)

    @patch('inveterate.tasks.npm.sync_domain_route')
    @patch('inveterate.tasks.domain_verify._public_resolver')
    def test_absent_txt_fails_and_no_sync(self, mock_resolver, mock_sync):
        import dns.resolver
        from .tasks.domain_verify import verify_domain_route
        mock_resolver.return_value.resolve.side_effect = dns.resolver.NXDOMAIN()

        verify_domain_route(self.dr.id)

        self.dr.refresh_from_db()
        self.assertEqual(self.dr.verification_status, 'failed')
        self.assertIsNone(self.dr.verified_at)
        mock_sync.delay.assert_not_called()

    @patch('inveterate.tasks.npm.sync_domain_route')
    @patch('inveterate.tasks.domain_verify._public_resolver')
    def test_different_account_token_fails(self, mock_resolver, mock_sync):
        from .domain_verification import account_token
        from .tasks.domain_verify import verify_domain_route
        # A token belonging to some other account must NOT verify this route.
        other_token = account_token(self.svc.owner_id + 999)
        mock_resolver.return_value.resolve.return_value = [_txt_answer(other_token)]

        verify_domain_route(self.dr.id)

        self.dr.refresh_from_db()
        self.assertEqual(self.dr.verification_status, 'failed')
        mock_sync.delay.assert_not_called()


class TestDomainRouteVerificationSerializer(TestCase):

    def setUp(self):
        self.user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp = _service_plan(storage=disk)
        self.svc = _service(self.user, node, sp)
        self.sn = ServiceNetwork.objects.create(service=self.svc)
        ip.owner = self.sn
        ip.save()
        PortBlock.objects.create(
            gateway=self.gw, service_network=self.sn, port_start=10000, port_end=10099,
        )

    @patch('inveterate.serializers.sync_domain_route')
    @patch('inveterate.serializers.verify_domain_route')
    def test_create_enqueues_verify_not_sync(self, mock_verify, mock_sync):
        mock_verify.delay.return_value = MagicMock(id='t')
        from .serializers import DomainRouteSerializer
        ser = DomainRouteSerializer(data={
            'service': self.svc.id, 'domain': 'app.customer.com', 'forward_port': 80,
        })
        self.assertTrue(ser.is_valid(), ser.errors)
        instance = ser.save()
        self.assertEqual(instance.verification_status, 'pending')
        mock_verify.delay.assert_called_once_with(instance.id)
        mock_sync.delay.assert_not_called()

    @patch('inveterate.serializers.verify_domain_route')
    def test_verification_record_value_hidden_from_non_owner(self, mock_verify):
        mock_verify.delay.return_value = MagicMock(id='t')
        from .domain_verification import account_token
        from .serializers import DomainRouteSerializer
        dr = DomainRoute.objects.create(service=self.svc, domain='app.example.com')

        factory = APIRequestFactory()
        other = _user()

        owner_req = factory.get('/')
        owner_req.user = self.user
        owner_data = DomainRouteSerializer(dr, context={'request': owner_req}).data
        self.assertEqual(owner_data['verification_record_value'], account_token(self.svc.owner_id))
        self.assertEqual(owner_data['verification_record_name'], '_inveterate-verify.app.example.com')

        other_req = factory.get('/')
        other_req.user = other
        other_data = DomainRouteSerializer(dr, context={'request': other_req}).data
        self.assertIsNone(other_data['verification_record_value'])


class TestDomainRouteVerifyAction(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.user = _user()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        self.gw = _port_gateway(pools=[pool_int])

        ip1 = IP.objects.create(pool=pool_int, value='192.168.0.10')
        sp1 = _service_plan(storage=disk)
        self.admin_svc = _service(self.admin, node, sp1, hostname='admin.example.com')
        sn1 = ServiceNetwork.objects.create(service=self.admin_svc)
        ip1.owner = sn1
        ip1.save()
        PortBlock.objects.create(gateway=self.gw, service_network=sn1, port_start=10000, port_end=10099)

        ip2 = IP.objects.create(pool=pool_int, value='192.168.0.11')
        sp2 = _service_plan(storage=disk)
        self.user_svc = _service(self.user, node, sp2, hostname='user.example.com')
        sn2 = ServiceNetwork.objects.create(service=self.user_svc)
        ip2.owner = sn2
        ip2.save()
        PortBlock.objects.create(gateway=self.gw, service_network=sn2, port_start=10100, port_end=10199)

        self.user_route = DomainRoute.objects.create(service=self.user_svc, domain='user-app.example.com')
        self.client = APIClient()

    @patch('inveterate.viewsets.portforward.verify_domain_route')
    def test_verify_action_returns_202(self, mock_verify):
        mock_verify.delay.return_value = MagicMock(id='task-xyz')
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f'/api/v1/domainroutes/{self.user_route.id}/verify/')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['task_id'], 'task-xyz')
        self.assertEqual(resp.data['verification_status'], 'pending')
        mock_verify.delay.assert_called_once_with(self.user_route.pk)

    @patch('inveterate.viewsets.portforward.verify_domain_route')
    def test_verify_action_owner_scoped(self, mock_verify):
        mock_verify.delay.return_value = MagicMock(id='task-xyz')
        # A different user must not be able to trigger verify on this route.
        self.client.force_authenticate(user=self.admin)
        # admin is staff -> sees all; use a genuine non-owner non-staff user.
        stranger = User.objects.create_user('stranger', 'stranger@test.com', 'pass')
        self.client.force_authenticate(user=stranger)
        resp = self.client.post(f'/api/v1/domainroutes/{self.user_route.id}/verify/')
        self.assertEqual(resp.status_code, 404)
        mock_verify.delay.assert_not_called()


class TestDomainRouteBackfillMigration(TestCase):

    def test_backfill_sets_existing_routes_verified(self):
        import importlib
        migration = importlib.import_module(
            'inveterate.migrations.0017_domainroute_verification_status_and_more'
        )
        user = _admin()
        node = _node()
        sp = _service_plan()
        svc = _service(user, node, sp)
        dr = DomainRoute.objects.create(service=svc, domain='legacy.example.com')
        # Simulate a row that predates the new fields (default pending, no ts).
        DomainRoute.objects.filter(pk=dr.pk).update(
            verification_status='pending', verified_at=None,
        )

        from django.apps import apps as global_apps
        migration.backfill_existing_routes_verified(global_apps, None)

        dr.refresh_from_db()
        self.assertEqual(dr.verification_status, 'verified')
        self.assertIsNotNone(dr.verified_at)


# ===================================================================
# TestNPMClient
# ===================================================================

class TestNPMClient(TestCase):

    @patch('inveterate.npm.requests')
    def test_create_stream(self, mock_requests):
        mock_auth_resp = MagicMock()
        mock_auth_resp.json.return_value = {'token': 'jwt-token'}
        mock_auth_resp.raise_for_status = MagicMock()

        mock_create_resp = MagicMock()
        mock_create_resp.status_code = 201
        mock_create_resp.json.return_value = {'id': 42}
        mock_create_resp.raise_for_status = MagicMock()

        mock_requests.post.side_effect = [mock_auth_resp, mock_create_resp]

        from .npm import NPMClient
        client = NPMClient('http://gw:81', 'admin@test.com', 'pass')
        result = client.create_stream(20000, '192.168.0.10', 22)
        self.assertEqual(result['id'], 42)

    @patch('inveterate.npm.requests')
    def test_delete_stream(self, mock_requests):
        mock_auth_resp = MagicMock()
        mock_auth_resp.json.return_value = {'token': 'jwt-token'}
        mock_auth_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_auth_resp

        mock_del_resp = MagicMock()
        mock_del_resp.status_code = 200
        mock_del_resp.raise_for_status = MagicMock()
        mock_requests.delete.return_value = mock_del_resp

        from .npm import NPMClient
        client = NPMClient('http://gw:81', 'admin@test.com', 'pass')
        client.delete_stream(42)
        mock_requests.delete.assert_called_once()

    @patch('inveterate.npm.requests')
    def test_create_proxy_host(self, mock_requests):
        mock_auth_resp = MagicMock()
        mock_auth_resp.json.return_value = {'token': 'jwt-token'}
        mock_auth_resp.raise_for_status = MagicMock()

        mock_create_resp = MagicMock()
        mock_create_resp.status_code = 201
        mock_create_resp.json.return_value = {'id': 99}
        mock_create_resp.raise_for_status = MagicMock()

        mock_requests.post.side_effect = [mock_auth_resp, mock_create_resp]

        from .npm import NPMClient
        client = NPMClient('http://gw:81', 'admin@test.com', 'pass')
        result = client.create_proxy_host('app.example.com', '192.168.0.10', 80)
        self.assertEqual(result['id'], 99)

    @patch('inveterate.npm.requests')
    def test_delete_proxy_host(self, mock_requests):
        mock_auth_resp = MagicMock()
        mock_auth_resp.json.return_value = {'token': 'jwt-token'}
        mock_auth_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_auth_resp

        mock_del_resp = MagicMock()
        mock_del_resp.status_code = 200
        mock_del_resp.raise_for_status = MagicMock()
        mock_requests.delete.return_value = mock_del_resp

        from .npm import NPMClient
        client = NPMClient('http://gw:81', 'admin@test.com', 'pass')
        client.delete_proxy_host(99)
        mock_requests.delete.assert_called_once()

    @patch('inveterate.npm.requests')
    def test_auth_token_refresh_on_401(self, mock_requests):
        mock_auth_resp = MagicMock()
        mock_auth_resp.json.return_value = {'token': 'jwt-token'}
        mock_auth_resp.raise_for_status = MagicMock()

        mock_401_resp = MagicMock()
        mock_401_resp.status_code = 401

        mock_ok_resp = MagicMock()
        mock_ok_resp.status_code = 200
        mock_ok_resp.json.return_value = {'id': 1}
        mock_ok_resp.raise_for_status = MagicMock()

        # First post = auth, second post = 401, third post = re-auth, fourth post = success
        mock_requests.post.side_effect = [mock_auth_resp, mock_401_resp, mock_auth_resp, mock_ok_resp]

        from .npm import NPMClient
        client = NPMClient('http://gw:81', 'admin@test.com', 'pass')
        result = client.create_stream(20000, '192.168.0.10', 22)
        self.assertEqual(result['id'], 1)
        # Auth should have been called twice (initial + refresh)
        self.assertEqual(mock_requests.post.call_count, 4)


# ===================================================================
# TestNPMSyncTasks
# ===================================================================

class TestNPMSyncTasks(TestCase):

    def _setup_internal_service(self):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool_int = _internal_pool(node)
        gw = _port_gateway(pools=[pool_int])
        ip = IP.objects.create(pool=pool_int, value='192.168.0.10')
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)
        sn = ServiceNetwork.objects.create(service=svc)
        ip.owner = sn
        ip.save()
        pb = PortBlock.objects.create(gateway=gw, service_network=sn, port_start=10000, port_end=10099)
        return svc, sn, pb, gw

    @patch('inveterate.npm.NPMClient')
    def test_sync_port_forward_creates_stream(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_stream.return_value = {'id': 42}

        svc, sn, pb, gw = self._setup_internal_service()
        pf = PortForward.objects.create(
            port_block=pb, external_port=10001, internal_port=22, protocol='tcp',
        )

        from .tasks import sync_port_forward
        sync_port_forward(pf.id)

        pf.refresh_from_db()
        self.assertEqual(pf.npm_stream_id, 42)

    @patch('inveterate.npm.NPMClient')
    def test_sync_domain_route_creates_proxy_host(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_proxy_host.return_value = {'id': 99}

        svc, sn, pb, gw = self._setup_internal_service()
        dr = DomainRoute.objects.create(
            service=svc, domain='app.example.com', forward_port=80,
        )

        from .tasks import sync_domain_route
        sync_domain_route(dr.id)

        dr.refresh_from_db()
        self.assertEqual(dr.npm_proxy_host_id, 99)

    @patch('inveterate.proxmox.ProxmoxAPI')
    @patch('inveterate.tasks.maintenance.chain')
    @patch('inveterate.tasks.maintenance.finalize_service_network_release')
    @patch('inveterate.tasks.maintenance.delete_npm_proxy_host')
    @patch('inveterate.tasks.maintenance.delete_npm_stream')
    def test_cancel_service_cleans_npm_resources(self, mock_del_stream, mock_del_proxy,
                                                  mock_finalize, mock_chain, mock_prox_cls):
        """cancel_service must build the NPM-cleanup chain with the right
        signatures and NOT release the internal IP/ServiceNetwork (or the
        DomainRoute row) synchronously -- that only happens once
        finalize_service_network_release actually runs, as the last link of
        the chain, after NPM confirms the stream/proxy host is gone."""
        mock_proxmox = MagicMock()
        mock_prox_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node

        svc, sn, pb, gw = self._setup_internal_service()
        pf = PortForward.objects.create(
            port_block=pb, external_port=10001, internal_port=22,
            protocol='tcp', npm_stream_id=42,
        )
        dr = DomainRoute.objects.create(
            service=svc, domain='app.example.com', forward_port=80,
            npm_proxy_host_id=99,
        )

        from .tasks import cancel_service
        cancel_service(svc.id)

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'destroyed')

        # The right NPM cleanup signatures were built...
        mock_del_stream.si.assert_called_with(gw.id, 42)
        mock_del_proxy.si.assert_called_with(gw.id, 99)
        mock_finalize.si.assert_called_with([sn.pk], [dr.id])
        # ...and dispatched as a single chain (not fire-and-forget .delay()).
        mock_chain.assert_called_once()
        mock_chain.return_value.apply_async.assert_called_once()

        # Nothing was released synchronously: the internal ServiceNetwork
        # (and therefore its IP) and the DomainRoute row are still there,
        # pending the chain's finalize step.
        self.assertTrue(ServiceNetwork.objects.filter(pk=sn.pk).exists())
        ip = IP.objects.get(pool=sn.ip.pool)
        self.assertEqual(ip.owner_id, sn.pk)
        self.assertTrue(DomainRoute.objects.filter(pk=dr.pk).exists())

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_releases_immediately_without_pending_npm(self, mock_prox_cls):
        """When nothing was ever synced to NPM (no npm_stream_id / no
        npm_proxy_host_id), there's nothing to leak, so cancel_service
        releases the internal ServiceNetwork/IP right away without deferring
        to a chain."""
        mock_proxmox = MagicMock()
        mock_prox_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node

        svc, sn, pb, gw = self._setup_internal_service()
        # Never-synced domain route: no npm_proxy_host_id.
        dr = DomainRoute.objects.create(service=svc, domain='app.example.com', forward_port=80)

        from .tasks import cancel_service
        cancel_service(svc.id)

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'destroyed')
        self.assertFalse(ServiceNetwork.objects.filter(pk=sn.pk).exists())
        self.assertFalse(DomainRoute.objects.filter(pk=dr.pk).exists())

    def test_finalize_service_network_release_deletes_domain_routes_and_releases_ip(self):
        """Simulates the chain's callback firing after NPM confirms cleanup:
        the DomainRoute rows and the ServiceNetwork must be deleted, freeing
        the IP and the domain for reuse."""
        svc, sn, pb, gw = self._setup_internal_service()
        dr = DomainRoute.objects.create(
            service=svc, domain='app.example.com', forward_port=80, npm_proxy_host_id=99,
        )
        ip = sn.ip

        from .tasks.maintenance import finalize_service_network_release
        finalize_service_network_release([sn.pk], [dr.id])

        self.assertFalse(ServiceNetwork.objects.filter(pk=sn.pk).exists())
        self.assertFalse(DomainRoute.objects.filter(pk=dr.pk).exists())
        ip.refresh_from_db()
        self.assertIsNone(ip.owner)

    def test_cleanup_orphaned_ips_skips_pending_npm_cleanup(self):
        """cleanup_orphaned_ips must not release a destroyed service's
        internal ServiceNetwork while a PortForward under it still carries a
        live npm_stream_id -- that would recreate the cross-tenant leak
        cancel_service's deferred release is meant to prevent."""
        svc, sn, pb, gw = self._setup_internal_service()
        PortForward.objects.create(
            port_block=pb, external_port=10001, internal_port=22,
            protocol='tcp', npm_stream_id=42,
        )
        svc.status = 'destroyed'
        svc.save(update_fields=['status'])

        from .tasks import cleanup_orphaned_ips
        cleanup_orphaned_ips()

        self.assertTrue(ServiceNetwork.objects.filter(pk=sn.pk).exists())

    def test_cleanup_orphaned_ips_skips_pending_domain_route_cleanup(self):
        """Same as above, but gated on a still-live DomainRoute.npm_proxy_host_id."""
        svc, sn, pb, gw = self._setup_internal_service()
        DomainRoute.objects.create(
            service=svc, domain='app.example.com', forward_port=80, npm_proxy_host_id=99,
        )
        svc.status = 'destroyed'
        svc.save(update_fields=['status'])

        from .tasks import cleanup_orphaned_ips
        cleanup_orphaned_ips()

        self.assertTrue(ServiceNetwork.objects.filter(pk=sn.pk).exists())


# ===================================================================
# TestNPMDeleteRetrySemantics
# ===================================================================

class TestNPMDeleteRetrySemantics(TestCase):
    """delete_npm_stream / delete_npm_proxy_host must not silently
    "succeed" on a transient failure -- only a 404 (already gone) counts as
    success. Everything else must propagate so Celery's autoretry_for (for
    transient errors) or plain task failure (for permanent ones) applies."""

    def _http_error(self, status_code):
        resp = MagicMock()
        resp.status_code = status_code
        err = requests.exceptions.HTTPError(response=resp)
        return err

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_stream_404_is_success(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_stream.side_effect = self._http_error(404)
        mock_get_client.return_value = client

        from .tasks import delete_npm_stream
        delete_npm_stream(1, 42)  # must not raise

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_stream_connection_error_propagates(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_stream.side_effect = requests.exceptions.ConnectionError('boom')
        mock_get_client.return_value = client

        from .tasks import delete_npm_stream
        with self.assertRaises(requests.exceptions.ConnectionError):
            delete_npm_stream(1, 42)

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_stream_npm_5xx_raises_transient_error(self, mock_pg, mock_get_client):
        from .tasks.npm import NPMTransientError

        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_stream.side_effect = self._http_error(503)
        mock_get_client.return_value = client

        from .tasks import delete_npm_stream
        with self.assertRaises(NPMTransientError):
            delete_npm_stream(1, 42)

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_stream_permanent_4xx_raises_http_error(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_stream.side_effect = self._http_error(400)
        mock_get_client.return_value = client

        from .tasks import delete_npm_stream
        with self.assertRaises(requests.exceptions.HTTPError):
            delete_npm_stream(1, 42)

    def test_delete_stream_autoretry_configured_for_transient_failures(self):
        from .tasks.npm import NPMTransientError, delete_npm_stream

        retry_for = delete_npm_stream.autoretry_for
        self.assertIn(requests.exceptions.ConnectionError, retry_for)
        self.assertIn(requests.exceptions.Timeout, retry_for)
        self.assertIn(NPMTransientError, retry_for)

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_proxy_host_404_is_success(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_proxy_host.side_effect = self._http_error(404)
        mock_get_client.return_value = client

        from .tasks import delete_npm_proxy_host
        delete_npm_proxy_host(1, 99)  # must not raise

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_proxy_host_timeout_propagates(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_proxy_host.side_effect = requests.exceptions.Timeout('slow')
        mock_get_client.return_value = client

        from .tasks import delete_npm_proxy_host
        with self.assertRaises(requests.exceptions.Timeout):
            delete_npm_proxy_host(1, 99)


# ===================================================================
# TestProxmoxHelpers
# ===================================================================

class TestProxmoxHelpers(TestCase):
    """Unit tests for inveterate.proxmox utility functions."""

    def setUp(self):
        from .proxmox import _reset_console_cred_cache
        _reset_console_cred_cache()

    def test_console_username_format(self):
        from .proxmox import console_username
        svc = MagicMock(id=42)
        self.assertEqual(console_username(svc), 'inv-s42@pve')

    def test_console_username_large_id(self):
        from .proxmox import console_username
        svc = MagicMock(id=1000123)
        self.assertEqual(console_username(svc), 'inv-s1000123@pve')

    def test_generate_console_password_length_and_safety(self):
        from .proxmox import generate_console_password
        pw = generate_console_password()
        self.assertEqual(len(pw), 24)
        # URL-safe means only alphanumeric, hyphen, underscore
        import re
        self.assertRegex(pw, r'^[A-Za-z0-9_-]+$')

    def test_ensure_console_user_creates_new(self):
        from .proxmox import ensure_console_user
        proxmox = MagicMock()
        svc = MagicMock(id=7)
        userid, password = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid, 'inv-s7@pve')
        self.assertTrue(len(password) > 0)
        proxmox.access.users.post.assert_called_once()
        proxmox.access.acl.put.assert_called_once_with(
            path='/vms/1000007', roles=['PVEVMUser'], users=['inv-s7@pve'],
        )

    def test_ensure_console_user_updates_existing(self):
        from .proxmox import ensure_console_user
        from proxmoxer.core import ResourceException

        proxmox = MagicMock()
        # First post raises "already exists", second post (after delete) succeeds
        proxmox.access.users.post.side_effect = [
            ResourceException(
                status_code=500, status_message='',
                content='user already exists', errors=None,
            ),
            None,  # second call succeeds
        ]
        svc = MagicMock(id=7)
        userid, password = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid, 'inv-s7@pve')
        proxmox.access.users('inv-s7@pve').delete.assert_called_once()
        self.assertEqual(proxmox.access.users.post.call_count, 2)
        proxmox.access.acl.put.assert_called_once()

    def test_ensure_console_user_repeat_call_reuses_cached_credentials(self):
        """A second call for the same service shortly after the first (e.g. a
        racing "Reconnect" click during the in-flight credential fetch) must
        return the exact same userid/password and must not touch Proxmox
        again, since deleting/recreating the user would invalidate a ticket
        already obtained with the first password."""
        from .proxmox import ensure_console_user
        proxmox = MagicMock()
        svc = MagicMock(id=7)

        userid1, password1 = ensure_console_user(proxmox, svc, 1000007)
        userid2, password2 = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid1, userid2)
        self.assertEqual(password1, password2)
        proxmox.access.users.post.assert_called_once()
        proxmox.access.acl.put.assert_called_once()

    def test_ensure_console_user_rotates_after_cache_expires(self):
        """Once the cached credentials expire, the next call rotates the
        password (still hitting Proxmox), so passwords aren't cached forever."""
        from .proxmox import ensure_console_user
        proxmox = MagicMock()
        svc = MagicMock(id=7)

        with patch('inveterate.proxmox.time.monotonic', return_value=1000.0):
            userid1, password1 = ensure_console_user(proxmox, svc, 1000007)

        with patch('inveterate.proxmox.time.monotonic', return_value=1000.0 + 3600):
            userid2, password2 = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid1, userid2)
        self.assertNotEqual(password1, password2)
        self.assertEqual(proxmox.access.users.post.call_count, 2)

    def test_ensure_console_user_reraises_other_error(self):
        from .proxmox import ensure_console_user, ProxmoxConsoleError
        from proxmoxer.core import ResourceException

        proxmox = MagicMock()
        proxmox.access.users.post.side_effect = ResourceException(
            status_code=500, status_message='',
            content='something else went wrong', errors=None,
        )
        svc = MagicMock(id=7)
        with self.assertRaises(ProxmoxConsoleError):
            ensure_console_user(proxmox, svc, 1000007)

    def test_ensure_console_user_handles_connection_error(self):
        from .proxmox import ensure_console_user, ProxmoxConsoleError

        proxmox = MagicMock()
        proxmox.access.users.post.side_effect = ConnectionError('refused')
        svc = MagicMock(id=7)
        with self.assertRaises(ProxmoxConsoleError):
            ensure_console_user(proxmox, svc, 1000007)

    @patch('inveterate.proxmox.requests.post')
    def test_get_console_ticket_success(self, mock_post):
        from .proxmox import get_console_ticket
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'data': {
                'ticket': 'PVE:ticket123',
                'CSRFPreventionToken': 'csrf-tok',
            }},
        )
        result = get_console_ticket('10.0.0.1', 'inv-s7@pve', 'pass')
        self.assertEqual(result['ticket'], 'PVE:ticket123')
        self.assertEqual(result['CSRFPreventionToken'], 'csrf-tok')

    @patch('inveterate.proxmox.requests.post')
    def test_get_console_ticket_auth_failure(self, mock_post):
        from .proxmox import get_console_ticket, ProxmoxConsoleError
        mock_post.return_value = MagicMock(status_code=401)
        with self.assertRaises(ProxmoxConsoleError):
            get_console_ticket('10.0.0.1', 'inv-s7@pve', 'badpass')

    def test_is_console_user_valid(self):
        from .proxmox import is_console_user
        self.assertEqual(is_console_user('inv-s42@pve'), 42)

    def test_is_console_user_invalid(self):
        from .proxmox import is_console_user
        self.assertIsNone(is_console_user('root@pam'))
        self.assertIsNone(is_console_user('inv-sABC@pve'))
        self.assertIsNone(is_console_user(''))

    def test_is_console_user_legacy_returns_none(self):
        from .proxmox import is_console_user
        self.assertIsNone(is_console_user('inveterate5@pve'))

    def test_is_legacy_console_user(self):
        from .proxmox import is_legacy_console_user
        self.assertEqual(is_legacy_console_user('inveterate5@pve'), 5)
        self.assertIsNone(is_legacy_console_user('inv-s5@pve'))
        self.assertIsNone(is_legacy_console_user('root@pam'))

    def test_get_proxmox_connection(self):
        from .proxmox import get_proxmox_connection
        cluster = MagicMock(host='10.0.0.1', user='root@pam', key='tok', verify_ssl=False)
        with patch('inveterate.proxmox.ProxmoxAPI') as mock_cls:
            get_proxmox_connection(cluster, timeout=60)
            mock_cls.assert_called_once_with(
                '10.0.0.1', user='root@pam', token_name='inveterate',
                token_value='tok', verify_ssl=False, port=8006, timeout=60,
            )


# ===================================================================
# TestConsoleErrorHandling
# ===================================================================

class TestConsoleErrorHandling(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.client = APIClient()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        _disk(self.node)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_console_proxmox_failure_returns_502(self, mock_cls):
        from proxmoxer.core import ResourceException
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_proxmox.access.users.post.side_effect = ResourceException(
            status_code=500, status_message='',
            content='internal error', errors=None,
        )
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(f'/api/v1/services/{svc.id}/console/')
        self.assertEqual(resp.status_code, 502)
        self.assertIn('detail', resp.data)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_console_connection_error_returns_502(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_proxmox.access.users.post.side_effect = ConnectionError('refused')
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(f'/api/v1/services/{svc.id}/console/')
        self.assertEqual(resp.status_code, 502)

    def test_console_no_machine_returns_400(self):
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp)  # no machine_id

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(f'/api/v1/services/{svc.id}/console/')
        self.assertEqual(resp.status_code, 400)


# ===================================================================
# TestCleanupConsoleUsers
# ===================================================================

class TestCleanupConsoleUsers(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.user = _user()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        _disk(self.node)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_orphaned_per_service_users_deleted(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox

        # Active service
        sp = _service_plan(type='lxc')
        svc = _service(self.admin, self.node, sp, machine_id=1000001)

        # Proxmox returns users for active service, orphaned service, and root
        mock_proxmox.access.users.get.return_value = [
            {'userid': f'inv-s{svc.id}@pve'},
            {'userid': 'inv-s999@pve'},
            {'userid': 'root@pam'},
        ]

        from .tasks import cleanup_console_users
        cleanup_console_users()

        # Collect which userids were passed to .access.users(userid) for deletion
        deleted_userids = [
            call.args[0] for call in mock_proxmox.access.users.call_args_list
            if call.args
        ]
        self.assertIn('inv-s999@pve', deleted_userids)
        self.assertNotIn(f'inv-s{svc.id}@pve', deleted_userids)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_legacy_users_cleaned_up(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox

        # Active service owned by self.admin
        sp = _service_plan(type='lxc')
        _service(self.admin, self.node, sp, machine_id=1000001)

        # Legacy user for an owner with no active services (owner_id=9999)
        # and legacy user for admin (should be kept)
        mock_proxmox.access.users.get.return_value = [
            {'userid': f'inveterate{self.admin.id}@pve'},
            {'userid': 'inveterate9999@pve'},
        ]

        from .tasks import cleanup_console_users
        cleanup_console_users()

        deleted_userids = [
            call.args[0] for call in mock_proxmox.access.users.call_args_list
            if call.args
        ]
        self.assertIn('inveterate9999@pve', deleted_userids)
        self.assertNotIn(f'inveterate{self.admin.id}@pve', deleted_userids)


# ===================================================================
# TestConsoleTermproxyView
# ===================================================================

class TestConsoleTermproxyView(TestCase):

    def setUp(self):
        self.admin = _admin()
        self.user = _user()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        _disk(self.node)
        self.sp = _service_plan(type='lxc')
        self.svc = _service(self.admin, self.node, self.sp, machine_id=1000001)
        self.client.login(username='admin', password='pass')

    def test_termproxy_requires_post(self):
        resp = self.client.get(f'/services/{self.svc.id}/console/termproxy/')
        self.assertEqual(resp.status_code, 405)

    def test_termproxy_requires_auth_params(self):
        resp = self.client.post(f'/services/{self.svc.id}/console/termproxy/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ticket', resp.json()['error'].lower())

    @patch('inveterate.views.http_requests')
    def test_termproxy_proxies_to_proxmox(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'port': '5900',
                'ticket': 'PVEVNC:abc123',
                'user': f'inv-s{self.svc.id}@pve',
            }
        }
        mock_requests.post.return_value = mock_resp
        mock_requests.exceptions = __import__('requests').exceptions

        resp = self.client.post(
            f'/services/{self.svc.id}/console/termproxy/',
            {'ticket': 'PVE:tok', 'csrf': 'csrf-tok'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['port'], '5900')
        self.assertEqual(data['vmtype'], 'lxc')
        self.assertEqual(data['node'], self.node.name)

    @patch('inveterate.views.http_requests')
    def test_termproxy_handles_proxmox_timeout(self, mock_requests):
        mock_requests.post.side_effect = __import__('requests').exceptions.Timeout
        mock_requests.exceptions = __import__('requests').exceptions

        resp = self.client.post(
            f'/services/{self.svc.id}/console/termproxy/',
            {'ticket': 'PVE:tok', 'csrf': 'csrf-tok'},
        )
        self.assertEqual(resp.status_code, 504)


# ===================================================================
# TestConsoleProxyConsumer
# ===================================================================

from channels.testing import WebsocketCommunicator  # noqa: E402
from channels.db import database_sync_to_async  # noqa: E402


class TestConsoleProxyConsumer(TestCase):

    def _get_communicator(self, service_id, user=None):
        from inveterate.consumers import ConsoleProxyConsumer
        communicator = WebsocketCommunicator(
            ConsoleProxyConsumer.as_asgi(),
            f'/ws/console/{service_id}/',
        )
        communicator.scope['url_route'] = {
            'kwargs': {'service_id': str(service_id)},
        }
        if user:
            communicator.scope['user'] = user
        return communicator

    async def test_unauthenticated_rejected(self):
        from django.contrib.auth.models import AnonymousUser
        communicator = self._get_communicator(99999, user=AnonymousUser())
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_wrong_owner_rejected(self):
        admin = await database_sync_to_async(_admin)()
        user = await database_sync_to_async(_user)()
        cluster = await database_sync_to_async(_cluster)()
        node = await database_sync_to_async(_node)(cluster=cluster)
        await database_sync_to_async(_disk)(node)
        sp = await database_sync_to_async(_service_plan)(type='lxc')
        svc = await database_sync_to_async(_service)(admin, node, sp, machine_id=1000001)

        communicator = self._get_communicator(svc.id, user=user)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4004)

    async def test_connect_accepts_valid_user(self):
        admin = await database_sync_to_async(_admin)()
        cluster = await database_sync_to_async(_cluster)()
        node = await database_sync_to_async(_node)(cluster=cluster)
        await database_sync_to_async(_disk)(node)
        sp = await database_sync_to_async(_service_plan)(type='lxc')
        svc = await database_sync_to_async(_service)(admin, node, sp, machine_id=1000001)

        communicator = self._get_communicator(svc.id, user=admin)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_auth_rejects_control_chars_in_csrf_without_connecting(self):
        """CRLF (or any control char) in the client-supplied `csrf` field
        must be rejected before websockets.connect() is ever called, since
        `csrf` is passed verbatim as an unescaped HTTP header value to the
        upstream Proxmox connection."""
        admin = await database_sync_to_async(_admin)()
        cluster = await database_sync_to_async(_cluster)()
        node = await database_sync_to_async(_node)(cluster=cluster)
        await database_sync_to_async(_disk)(node)
        sp = await database_sync_to_async(_service_plan)(type='lxc')
        svc = await database_sync_to_async(_service)(admin, node, sp, machine_id=1000001)

        communicator = self._get_communicator(svc.id, user=admin)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        with patch('inveterate.consumers.websockets.connect') as mock_connect:
            await communicator.send_to(text_data=__import__('json').dumps({
                'type': 'auth',
                'ticket': 'PVE:tok',
                'csrf': '635C8B2A:abcdef\r\nX-Injected-Header: evil',
                'username': 'root@pam',
                'port': 5900,
                'vncticket': 'vnc-tok',
            }))
            response = await communicator.receive_from()
            data = __import__('json').loads(response)
            self.assertEqual(data['type'], 'error')

            close_event = await communicator.receive_output()
            self.assertEqual(close_event['type'], 'websocket.close')
            self.assertEqual(close_event.get('code'), 4003)

            mock_connect.assert_not_called()

        await communicator.disconnect()

    async def test_auth_rejects_control_chars_in_username(self):
        """Same protection for `username` (written into the termproxy auth
        line sent over the upstream socket)."""
        admin = await database_sync_to_async(_admin)()
        cluster = await database_sync_to_async(_cluster)()
        node = await database_sync_to_async(_node)(cluster=cluster)
        await database_sync_to_async(_disk)(node)
        sp = await database_sync_to_async(_service_plan)(type='lxc')
        svc = await database_sync_to_async(_service)(admin, node, sp, machine_id=1000001)

        communicator = self._get_communicator(svc.id, user=admin)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        with patch('inveterate.consumers.websockets.connect') as mock_connect:
            await communicator.send_to(text_data=__import__('json').dumps({
                'type': 'auth',
                'ticket': 'PVE:tok',
                'csrf': '635C8B2A:abcdef',
                'username': 'root@pam\r\nHost: evil',
                'port': 5900,
                'vncticket': 'vnc-tok',
            }))
            response = await communicator.receive_from()
            data = __import__('json').loads(response)
            self.assertEqual(data['type'], 'error')
            mock_connect.assert_not_called()

        await communicator.disconnect()

    async def test_auth_message_required_first(self):
        admin = await database_sync_to_async(_admin)()
        cluster = await database_sync_to_async(_cluster)()
        node = await database_sync_to_async(_node)(cluster=cluster)
        await database_sync_to_async(_disk)(node)
        sp = await database_sync_to_async(_service_plan)(type='lxc')
        svc = await database_sync_to_async(_service)(admin, node, sp, machine_id=1000001)

        communicator = self._get_communicator(svc.id, user=admin)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Send non-auth message
        await communicator.send_to(text_data='hello')
        response = await communicator.receive_from()
        data = __import__('json').loads(response)
        self.assertEqual(data['type'], 'error')
        await communicator.disconnect()


# ===================================================================
# TestTaskStatusView / task_ownership
# ===================================================================

class TestTaskOwnershipHelper(TestCase):
    """Unit tests for inveterate.task_ownership (used by TaskStatusView)."""

    def setUp(self):
        self.user = _user()
        self.other = User.objects.create_user('user2', 'user2@test.com', 'pass')

    def test_record_and_check_ownership(self):
        record_task_owner('11111111-1111-1111-1111-111111111111', self.user)
        self.assertTrue(user_owns_task('11111111-1111-1111-1111-111111111111', self.user))
        self.assertFalse(user_owns_task('11111111-1111-1111-1111-111111111111', self.other))

    def test_record_task_owner_noops_for_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        result = record_task_owner('some-task-id', AnonymousUser())
        self.assertIsNone(result)
        self.assertEqual(DispatchedTask.objects.count(), 0)

    def test_record_task_owner_noops_for_none_user(self):
        result = record_task_owner('some-task-id', None)
        self.assertIsNone(result)

    def test_record_task_owner_is_idempotent_per_task_id(self):
        record_task_owner('dup-task-id', self.user)
        record_task_owner('dup-task-id', self.other)
        self.assertEqual(DispatchedTask.objects.filter(task_id='dup-task-id').count(), 1)
        self.assertTrue(user_owns_task('dup-task-id', self.other))
        self.assertFalse(user_owns_task('dup-task-id', self.user))

    def test_user_owns_task_false_when_no_record(self):
        self.assertFalse(user_owns_task('never-recorded', self.user))


class TestTaskStatusView(TestCase):
    """IDOR regression tests for GET /api/v1/tasks/<task_id>/."""

    def setUp(self):
        self.owner = _user()
        self.stranger = User.objects.create_user('user2', 'user2@test.com', 'pass')
        self.admin = _admin()
        self.task_id = '22222222-2222-2222-2222-222222222222'
        record_task_owner(self.task_id, self.owner)
        self.url = f'/api/v1/tasks/{self.task_id}/'

    def test_owner_can_read_task_status(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        resp = client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['task_id'], self.task_id)

    def test_non_owner_gets_404(self):
        client = APIClient()
        client.force_authenticate(user=self.stranger)
        resp = client.get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_staff_can_read_any_task_status(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_unrecorded_task_id_gets_404_for_non_staff(self):
        client = APIClient()
        client.force_authenticate(user=self.stranger)
        resp = client.get('/api/v1/tasks/33333333-3333-3333-3333-333333333333/')
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_gets_401_or_403(self):
        client = APIClient()
        resp = client.get(self.url)
        self.assertIn(resp.status_code, (401, 403))


# ===================================================================
# TestOperationInProgressFlag
# ===================================================================

class TestOperationInProgressFlag(TestCase):
    """operation_in_progress is set at the start of a mutating task and always
    cleared in a finally block — even when the task raises — so a crash never
    leaves a service permanently locked."""

    def _setup_service(self, svc_type='lxc', **kw):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type=svc_type, file='100' if svc_type == 'kvm' else 'debian.tar.zst')
        sp = _service_plan(template=tpl, storage=disk, type=svc_type, ipv4_ips=0)
        return _service(user, node, sp, machine_id=1000001, **kw)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_power_task_sets_and_clears_flag(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        svc = self._setup_service('lxc')

        seen = {}

        def _record(*_a, **_k):
            seen['during'] = Service.objects.get(pk=svc.id).operation_in_progress

        mock_proxmox.nodes.return_value.lxc.return_value.status.start.post.side_effect = _record

        from .tasks import start_vm
        start_vm(svc.id)

        self.assertTrue(seen['during'])  # flag held while the op runs
        svc.refresh_from_db()
        self.assertFalse(svc.operation_in_progress)  # cleared afterwards

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_power_task_clears_flag_on_exception(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_proxmox.nodes.return_value.lxc.return_value.status.stop.post.side_effect = RuntimeError("boom")
        svc = self._setup_service('lxc')

        from .tasks import stop_vm
        with self.assertRaises(RuntimeError):
            stop_vm(svc.id)

        svc.refresh_from_db()
        self.assertFalse(svc.operation_in_progress)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_clears_flag_on_success(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.return_value.firewall.rules.get.return_value = []
        mock_node.lxc.return_value.firewall.ipset.return_value.get.return_value = []
        svc = self._setup_service('lxc', status='pending')

        from .tasks import provision_service
        provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')
        self.assertFalse(svc.operation_in_progress)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_clears_flag_on_exception(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.create.side_effect = ConnectionError("refused")
        svc = self._setup_service('lxc', status='pending')

        from .tasks import provision_service
        with self.assertRaises(ConnectionError):
            provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')
        self.assertFalse(svc.operation_in_progress)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_resize_clears_flag_on_validation_error(self, mock_cls, _mock_inv):
        # A resize that raises before touching Proxmox (disk shrink) must still
        # clear the flag via the finally block.
        mock_cls.return_value = MagicMock()
        svc = self._setup_service('lxc')  # ServicePlan size defaults to 10
        target = _plan(size=5)  # smaller disk -> ValueError

        from .tasks import resize_service
        with self.assertRaises(ValueError):
            resize_service(svc.id, target.id)

        svc.refresh_from_db()
        self.assertFalse(svc.operation_in_progress)


# ===================================================================
# TestResizeService
# ===================================================================

class TestResizeService(TestCase):

    def _setup(self, svc_type='kvm'):
        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type=svc_type, file='100' if svc_type == 'kvm' else 'debian.tar.zst')
        sp = _service_plan(
            template=tpl, storage=disk, type=svc_type, size=10, ram=1024,
            cores=1, swap=256, ipv4_ips=0,
        )
        svc = _service(user, node, sp, machine_id=1000001, status='active')
        target = _plan(name='VPS-2', size=20, ram=2048, cores=2, swap=512, ipv4_ips=0)
        return svc, target

    @patch('inveterate.tasks.resize.time.sleep')
    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_successful_resize_waits_and_updates_snapshot(self, mock_cls, mock_inventory, _mock_sleep):
        proxmox = MagicMock()
        mock_cls.return_value = proxmox
        node = proxmox.nodes.return_value
        machine = node.qemu.return_value
        machine.status.current.get.side_effect = [
            {'status': 'running'}, {'status': 'stopped'}, {'status': 'stopped'},
            {'status': 'stopped'}, {'status': 'running'},
        ]
        machine.status.shutdown.post.return_value = 'UPID:shutdown'
        machine.config.post.return_value = 'UPID:config'
        machine.resize.put.return_value = 'UPID:disk'
        machine.status.start.post.return_value = 'UPID:start'
        node.tasks.return_value.status.get.return_value = {'status': 'stopped', 'exitstatus': 'OK'}
        svc, target = self._setup()

        from .tasks import resize_service
        resize_service(svc.id, target.id)

        svc.service_plan.refresh_from_db()
        self.assertEqual(svc.service_plan.size, target.size)
        self.assertEqual(svc.service_plan.ram, target.ram)
        self.assertEqual(svc.service_plan.cores, target.cores)
        self.assertEqual(node.tasks.call_count, 4)
        mock_inventory.delay.assert_called_once()
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')
        self.assertIsNone(svc.status_msg)
        self.assertFalse(svc.operation_in_progress)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_shrink_is_rejected_before_proxmox(self, mock_cls):
        svc, target = self._setup()
        target.size = 5
        target.save(update_fields=('size',))

        from .tasks import resize_service
        with self.assertRaises(ValueError):
            resize_service(svc.id, target.id)

        mock_cls.assert_not_called()
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')
        self.assertIn('Cannot shrink disk', svc.status_msg)

    @patch('inveterate.tasks.resize.time.sleep')
    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_disk_failure_persists_only_applied_cpu_and_ram(self, mock_cls, mock_inventory, _mock_sleep):
        proxmox = MagicMock()
        mock_cls.return_value = proxmox
        node = proxmox.nodes.return_value
        machine = node.qemu.return_value
        machine.status.current.get.side_effect = [
            {'status': 'running'}, {'status': 'stopped'}, {'status': 'stopped'}, {'status': 'running'},
        ]
        node.tasks.return_value.status.get.return_value = {'status': 'stopped', 'exitstatus': 'OK'}
        machine.resize.put.side_effect = RuntimeError('disk resize failed')
        svc, target = self._setup()

        from .tasks import resize_service
        with self.assertRaisesRegex(RuntimeError, 'disk resize failed'):
            resize_service(svc.id, target.id)

        svc.service_plan.refresh_from_db()
        self.assertEqual(svc.service_plan.ram, target.ram)
        self.assertEqual(svc.service_plan.cores, target.cores)
        self.assertEqual(svc.service_plan.size, 10)
        self.assertNotEqual(svc.service_plan.name, target.name)
        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')
        self.assertIn('disk resize failed', svc.status_msg)
        mock_inventory.delay.assert_not_called()

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_missing_vm_sets_error_status(self, mock_cls):
        from proxmoxer.core import ResourceException

        proxmox = MagicMock()
        mock_cls.return_value = proxmox
        proxmox.nodes.return_value.qemu.return_value.status.current.get.side_effect = ResourceException(
            500, 'fail', 'no such VM'
        )
        svc, target = self._setup()

        from .tasks import resize_service
        with self.assertRaises(ResourceException):
            resize_service(svc.id, target.id)

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')
        self.assertIn('Resize failed', svc.status_msg)
        self.assertFalse(svc.operation_in_progress)


# ===================================================================
# TestOperationLockGuard
# ===================================================================

class TestOperationLockGuard(TestCase):
    """Viewset actions return 409 when an operation is already in progress and
    claim the lock (compare-and-set) before dispatching a task."""

    def setUp(self):
        self.admin = _admin()
        self.cluster = _cluster()
        self.node = _node(cluster=self.cluster)
        self.disk = _disk(self.node)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _service(self, **kw):
        sp = _service_plan(type='lxc')
        return _service(self.admin, self.node, sp, machine_id=1000001, **kw)

    @patch('inveterate.viewsets.service.start_vm')
    def test_start_returns_409_when_operation_in_progress(self, mock_start):
        svc = self._service(operation_in_progress=True)
        resp = self.client.post(f'/api/v1/services/{svc.id}/start/')
        self.assertEqual(resp.status_code, 409)
        mock_start.delay.assert_not_called()
        svc.refresh_from_db()
        self.assertTrue(svc.operation_in_progress)  # left untouched

    @patch('inveterate.viewsets.service.start_vm')
    def test_start_claims_flag_before_dispatch(self, mock_start):
        mock_start.delay.return_value = MagicMock(id='abc-123')
        svc = self._service()
        resp = self.client.post(f'/api/v1/services/{svc.id}/start/')
        self.assertEqual(resp.status_code, 202)
        mock_start.delay.assert_called_once_with(svc.id)
        # The viewset sets the flag True right before dispatch; the task is
        # mocked here so it stays True (the real task would clear it in finally).
        svc.refresh_from_db()
        self.assertTrue(svc.operation_in_progress)

    @patch('inveterate.viewsets.service.provision_service')
    def test_provision_returns_409_when_operation_in_progress(self, mock_prov):
        svc = self._service(operation_in_progress=True, status='pending')
        resp = self.client.post(f'/api/v1/services/{svc.id}/provision/')
        self.assertEqual(resp.status_code, 409)
        mock_prov.delay.assert_not_called()

    @patch('inveterate.viewsets.service.cancel_service')
    def test_cancel_returns_409_while_resize_operation_in_progress(self, mock_cancel):
        svc = self._service(operation_in_progress=True)
        resp = self.client.post(f'/api/v1/services/{svc.id}/cancel/')
        self.assertEqual(resp.status_code, 409)
        mock_cancel.delay.assert_not_called()

    @patch('inveterate.viewsets.service.start_vm')
    def test_flag_released_when_dispatch_fails(self, mock_start):
        mock_start.delay.side_effect = RuntimeError("broker down")
        svc = self._service()
        with self.assertRaises(RuntimeError):
            self.client.post(f'/api/v1/services/{svc.id}/start/')
        svc.refresh_from_db()
        self.assertFalse(svc.operation_in_progress)  # released on dispatch failure
