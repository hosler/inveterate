from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

class TestCancelServiceSnippetCleanup(TestCase):

    @patch('inveterate.tasks.maintenance.delete_snippet')
    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_cleans_up_snippet(self, mock_cls, mock_delete):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.tasks.return_value.status.get.return_value = {'status': 'stopped', 'exitstatus': 'OK'}

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)

        from ..tasks import cancel_service
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
        mock_node.tasks.return_value.status.get.return_value = {'status': 'stopped', 'exitstatus': 'OK'}
        mock_delete.side_effect = Exception("ssh failed")

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)

        from ..tasks import cancel_service
        cancel_service(svc.id)

        svc.refresh_from_db()
        self.assertEqual(svc.status, 'destroyed')


# ===================================================================
# TestServiceSerializerApps
# ===================================================================

class TestCancelServiceIPRelease(TestCase):

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_releases_ips(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.qemu.return_value.delete.return_value = 'UPID:delete'
        mock_node.tasks.return_value.status.get.return_value = {
            'status': 'stopped', 'exitstatus': 'OK',
        }

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

        from ..tasks import cancel_service
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
    def test_cancel_service_retains_ips_when_delete_fails(self, mock_cls):
        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.qemu.return_value.delete.return_value = 'UPID:delete'
        mock_node.tasks.return_value.status.get.return_value = {
            'status': 'stopped', 'exitstatus': 'ERROR',
        }

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool = _ip_pool(node)
        ip = IP.objects.create(pool=pool, value='10.0.0.10')
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)
        sn = ServiceNetwork.objects.create(service=svc)
        ip.owner = sn
        ip.save()

        from ..tasks import cancel_service
        cancel_service(svc.id)

        svc.refresh_from_db()
        ip.refresh_from_db()
        self.assertEqual(svc.status, 'error')
        self.assertIn('ERROR', svc.status_msg)
        self.assertTrue(ServiceNetwork.objects.filter(pk=sn.pk).exists())
        self.assertEqual(ip.owner_id, sn.pk)

    @patch('inveterate.proxmox.ProxmoxAPI')
    def test_cancel_service_connection_error_during_poll_propagates(self, mock_cls):
        """A transient ConnectionError while polling the delete UPID must
        propagate so the task-level autoretry fires, not strand the service
        in a terminal error state."""
        from requests.exceptions import ConnectionError as RequestsConnectionError

        mock_proxmox = MagicMock()
        mock_cls.return_value = mock_proxmox
        mock_node = MagicMock()
        mock_proxmox.nodes.return_value = mock_node
        mock_node.qemu.return_value.delete.return_value = 'UPID:delete'
        mock_node.tasks.return_value.status.get.side_effect = RequestsConnectionError('reset')

        user = _admin()
        cluster = _cluster()
        node = _node(cluster=cluster)
        disk = _disk(node)
        pool = _ip_pool(node)
        ip = IP.objects.create(pool=pool, value='10.0.0.10')
        tpl = _template(type='kvm', file='100')
        sp = _service_plan(template=tpl, storage=disk, type='kvm')
        svc = _service(user, node, sp, machine_id=1000001)
        sn = ServiceNetwork.objects.create(service=svc)
        ip.owner = sn
        ip.save()

        from ..tasks import cancel_service
        with self.assertRaises(RequestsConnectionError):
            cancel_service(svc.id)

        svc.refresh_from_db()
        ip.refresh_from_db()
        self.assertNotEqual(svc.status, 'error')
        self.assertTrue(ServiceNetwork.objects.filter(pk=sn.pk).exists())
        self.assertEqual(ip.owner_id, sn.pk)

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

        from ..tasks import cancel_service
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

        from ..tasks import cleanup_orphaned_ips
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

        from ..tasks import cleanup_orphaned_ips
        cleanup_orphaned_ips()

        # Active service networks should be untouched
        self.assertEqual(ServiceNetwork.objects.filter(service=svc).count(), 1)
        ip1.refresh_from_db()
        self.assertIsNotNone(ip1.owner)


# ===================================================================
# TestSetupPeriodicTasks
# ===================================================================

