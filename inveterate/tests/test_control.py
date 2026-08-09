from unittest.mock import patch

from django.utils import timezone

from .helpers import TestCase, _admin, _disk, _node, _service, _service_plan
from ..tasks import reboot_vm, reset_vm, shutdown_vm, start_vm, stop_vm


class TestPowerOperations(TestCase):
    def setUp(self):
        self.node = _node()
        plan = _service_plan(storage=_disk(self.node), type="lxc")
        self.service = _service(
            _admin(), self.node, plan, machine_id=1000001,
        )

    def _claim_operation(self):
        self.service.operation_in_progress = True
        self.service.operation_started_at = timezone.now()
        self.service.save(update_fields=("operation_in_progress", "operation_started_at"))

    def _assert_claim_released(self):
        self.service.refresh_from_db()
        self.assertFalse(self.service.operation_in_progress)
        self.assertIsNone(self.service.operation_started_at)

    @patch("inveterate.proxmox.ProxmoxAPI")
    def test_power_operations_release_claim_after_success(self, proxmox_cls):
        machine = proxmox_cls.return_value.nodes.return_value.lxc.return_value
        operations = (
            (start_vm, machine.status.start.post),
            (stop_vm, machine.status.stop.post),
            (reset_vm, machine.status.reset.post),
            (shutdown_vm, machine.status.shutdown.post),
            (reboot_vm, machine.status.reboot.post),
        )

        for task, post in operations:
            with self.subTest(task=task.name):
                self._claim_operation()
                task(self.service.id)
                post.assert_called_once_with()
                post.reset_mock()
                self._assert_claim_released()

    @patch("inveterate.proxmox.ProxmoxAPI")
    def test_power_operations_release_claim_after_proxmox_exception(self, proxmox_cls):
        machine = proxmox_cls.return_value.nodes.return_value.lxc.return_value
        operations = (
            (start_vm, machine.status.start.post),
            (stop_vm, machine.status.stop.post),
            (reset_vm, machine.status.reset.post),
            (shutdown_vm, machine.status.shutdown.post),
            (reboot_vm, machine.status.reboot.post),
        )

        for task, post in operations:
            with self.subTest(task=task.name):
                self._claim_operation()
                post.side_effect = RuntimeError("Proxmox failure")
                with self.assertRaisesRegex(RuntimeError, "Proxmox failure"):
                    task(self.service.id)
                post.side_effect = None
                self._assert_claim_released()
