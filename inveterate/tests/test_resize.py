from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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

        from ..tasks import resize_service
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

        from ..tasks import resize_service
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

        from ..tasks import resize_service
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

        from ..tasks import resize_service
        with self.assertRaises(ResourceException):
            resize_service(svc.id, target.id)

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'error')
        self.assertIn('Resize failed', svc.status_msg)
        self.assertFalse(svc.operation_in_progress)


# ===================================================================
# TestOperationLockGuard
# ===================================================================

