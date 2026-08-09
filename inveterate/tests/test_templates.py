from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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

        from ..tasks import import_kvm_template
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

        from ..tasks import import_kvm_template
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

        from ..tasks import import_kvm_template
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

        from ..tasks import import_kvm_template
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
        from ..serializers import TemplateSerializer
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
        from ..serializers import TemplateSerializer
        data = {
            'name': 'Debian 12',
            'type': 'lxc',
            'file': 'debian-12-standard_12.2-1_amd64.tar.zst',
        }
        ser = TemplateSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        tpl = ser.save()
        self.assertEqual(tpl.status, 'ready')


