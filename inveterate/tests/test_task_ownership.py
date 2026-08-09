from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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
    """Provisioning holds the operation flag until success or terminal failure."""

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

        from ..tasks import start_vm
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

        from ..tasks import stop_vm
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

        from ..tasks import provision_service
        provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'active')
        self.assertFalse(svc.operation_in_progress)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_retry_preserves_networking_and_flag(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.create.side_effect = ConnectionError("refused")
        svc = self._setup_service('lxc', status='pending')
        pool = _ip_pool(svc.node)
        ip = IP.objects.create(pool=pool, value='10.0.0.10')
        network = ServiceNetwork.objects.create(service=svc)
        ip.owner = network
        ip.save(update_fields=['owner'])

        from ..tasks import provision_service
        with self.assertRaises(ConnectionError):
            provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertNotEqual(svc.status, 'error')
        self.assertTrue(svc.operation_in_progress)
        self.assertTrue(ServiceNetwork.objects.filter(pk=network.pk).exists())
        ip.refresh_from_db()
        self.assertEqual(ip.owner_id, network.pk)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_provision_terminal_connection_failure_releases_state(self, mock_cls, _mock_inv):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.lxc.create.side_effect = ConnectionError("refused")
        svc = self._setup_service('lxc', status='pending')
        pool = _ip_pool(svc.node)
        ip = IP.objects.create(pool=pool, value='10.0.0.10')
        network = ServiceNetwork.objects.create(service=svc)
        ip.owner = network
        ip.save(update_fields=['owner'])

        from ..tasks import provision_service
        with patch.object(provision_service, 'max_retries', 0):
            with self.assertRaises(ConnectionError):
                provision_service(svc.id, 'testpass')

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')
        self.assertFalse(svc.operation_in_progress)
        self.assertFalse(ServiceNetwork.objects.filter(pk=network.pk).exists())
        ip.refresh_from_db()
        self.assertIsNone(ip.owner_id)

    @patch('inveterate.tasks.calculate_inventory')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_resize_clears_flag_on_validation_error(self, mock_cls, _mock_inv):
        # A resize that raises before touching Proxmox (disk shrink) must still
        # clear the flag via the finally block.
        mock_cls.return_value = MagicMock()
        svc = self._setup_service('lxc')  # ServicePlan size defaults to 10
        target = _plan(size=5)  # smaller disk -> ValueError

        from ..tasks import resize_service
        with self.assertRaises(ValueError):
            resize_service(svc.id, target.id)

        svc.refresh_from_db()
        self.assertFalse(svc.operation_in_progress)


# ===================================================================
# TestResizeService
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
