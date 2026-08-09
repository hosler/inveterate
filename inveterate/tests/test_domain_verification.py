from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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

        from ..serializers import DomainRouteSerializer
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
        from ..serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'app.customer-example.com', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    @patch('inveterate.serializers.sync_domain_route')
    def test_malformed_domain_rejected(self, mock_sync):
        from ..serializers import DomainRouteSerializer
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
        from ..serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'portal.hosnet.dhos.me', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('domain', ser.errors)

    @override_settings(INVETERATE_RESERVED_DOMAINS=['hosnet.dhos.me'])
    @patch('inveterate.serializers.sync_domain_route')
    def test_reserved_domain_exact_match_rejected(self, mock_sync):
        from ..serializers import DomainRouteSerializer
        data = {'service': self.svc.id, 'domain': 'hosnet.dhos.me', 'forward_port': 80}
        ser = DomainRouteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('domain', ser.errors)

    @override_settings(INVETERATE_RESERVED_DOMAINS=['hosnet.dhos.me'])
    @patch('inveterate.serializers.sync_domain_route')
    def test_domain_reservation_is_case_insensitive(self, mock_sync):
        from ..serializers import DomainRouteSerializer
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
        from ..serializers import DomainRouteSerializer
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

class TestAccountToken(TestCase):

    @override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='')
    def test_deterministic_per_owner(self):
        from ..domain_verification import account_token
        self.assertEqual(account_token(7), account_token(7))
        self.assertTrue(account_token(7).startswith('inv-verify='))

    @override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='')
    def test_differs_across_owners(self):
        from ..domain_verification import account_token
        self.assertNotEqual(account_token(7), account_token(8))

    def test_changes_with_salt(self):
        from ..domain_verification import account_token
        with override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='a'):
            token_a = account_token(7)
        with override_settings(SECRET_KEY='fixed-secret', INVETERATE_DOMAIN_VERIFICATION_SALT='b'):
            token_b = account_token(7)
        self.assertNotEqual(token_a, token_b)

    @override_settings(INVETERATE_DOMAIN_VERIFICATION_LABEL='_inveterate-verify')
    def test_record_name(self):
        from ..domain_verification import verification_record_name
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
        from ..domain_verification import account_token
        from ..tasks.domain_verify import verify_domain_route
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
        from ..tasks.domain_verify import verify_domain_route
        mock_resolver.return_value.resolve.side_effect = dns.resolver.NXDOMAIN()

        verify_domain_route(self.dr.id)

        self.dr.refresh_from_db()
        self.assertEqual(self.dr.verification_status, 'failed')
        self.assertIsNone(self.dr.verified_at)
        mock_sync.delay.assert_not_called()

    @patch('inveterate.tasks.npm.sync_domain_route')
    @patch('inveterate.tasks.domain_verify._public_resolver')
    def test_different_account_token_fails(self, mock_resolver, mock_sync):
        from ..domain_verification import account_token
        from ..tasks.domain_verify import verify_domain_route
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
        from ..serializers import DomainRouteSerializer
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
        from ..domain_verification import account_token
        from ..serializers import DomainRouteSerializer
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

