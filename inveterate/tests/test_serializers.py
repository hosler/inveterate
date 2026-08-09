from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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
        from ..serializers import ServiceSerializer
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
        from ..serializers import ServiceSerializer
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
        from ..serializers import ServiceSerializer
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
        from ..serializers import ServiceSerializer
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

    @patch('inveterate.serializers.provision_service.delay')
    def test_create_dispatches_provision_on_commit(self, mock_delay):
        from ..serializers import ServiceSerializer
        request = self.factory.post('/api/v1/services/')
        request.user = self.user
        data = {
            'owner': self.user.id,
            'hostname': 'commit.example.com',
            'plan': self.plan.id,
            'template': self.template.name,
            'password': 'secret-password',
            'ssh_keys': ['ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest'],
        }
        ser = ServiceSerializer(data=data, context={'request': request})
        ser.is_valid(raise_exception=True)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            svc = ser.save()
            mock_delay.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        mock_delay.assert_called_once_with(
            svc.id,
            'secret-password',
            ssh_keys=['ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest'],
        )

    @patch('inveterate.serializers.provision_service.delay')
    def test_update_busy_service_returns_409_without_dispatch(self, mock_delay):
        sp = _service_plan(template=self.template, storage=self.disk)
        svc = _service(
            self.user, self.node, sp, operation_in_progress=True,
            hostname='old.example.com',
        )
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.patch(
            f'/api/v1/services/{svc.id}/', {'hostname': 'new.example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, 409)
        mock_delay.assert_not_called()
        svc.refresh_from_db()
        self.assertEqual(svc.hostname, 'old.example.com')

    @patch('inveterate.serializers.provision_service.delay')
    def test_update_dispatches_provision_on_commit(self, mock_delay):
        sp = _service_plan(template=self.template, storage=self.disk)
        svc = _service(self.user, self.node, sp, hostname='old.example.com')
        client = APIClient()
        client.force_authenticate(user=self.user)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = client.patch(
                f'/api/v1/services/{svc.id}/', {'hostname': 'new.example.com'},
                format='json',
            )
            mock_delay.assert_not_called()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(callbacks), 1)
        mock_delay.assert_called_once_with(svc.id, None, ssh_keys=None)
        svc.refresh_from_db()
        self.assertTrue(svc.operation_in_progress)

    @patch('inveterate.serializers.provision_service.delay')
    def test_metadata_only_update_does_not_provision(self, mock_delay):
        sp = _service_plan(template=self.template, storage=self.disk)
        svc = _service(self.user, self.node, sp, status='pending')
        client = APIClient()
        client.force_authenticate(user=self.user)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = client.patch(
                f'/api/v1/services/{svc.id}/', {'status': 'active'}, format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(callbacks, [])
        mock_delay.assert_not_called()

    @patch('inveterate.serializers.provision_service')
    def test_plan_name_read_field(self, mock_prov):
        mock_prov.delay.return_value = MagicMock(id='task-1')
        from ..serializers import ServiceSerializer
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
        from ..serializers import ServiceSerializer
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
        from ..serializers import ServiceSerializer
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

        from ..serializers import ServiceSerializer
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
        from ..serializers import ServiceSerializer
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

