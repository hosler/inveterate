from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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

