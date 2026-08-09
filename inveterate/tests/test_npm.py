from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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

        from ..npm import NPMClient
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

        from ..npm import NPMClient
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

        from ..npm import NPMClient
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

        from ..npm import NPMClient
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

        from ..npm import NPMClient
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

        from ..tasks import sync_port_forward
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

        from ..tasks import sync_domain_route
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
        mock_node.tasks.return_value.status.get.return_value = {'status': 'stopped', 'exitstatus': 'OK'}

        svc, sn, pb, gw = self._setup_internal_service()
        pf = PortForward.objects.create(
            port_block=pb, external_port=10001, internal_port=22,
            protocol='tcp', npm_stream_id=42,
        )
        dr = DomainRoute.objects.create(
            service=svc, domain='app.example.com', forward_port=80,
            npm_proxy_host_id=99,
        )

        from ..tasks import cancel_service
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
        mock_node.tasks.return_value.status.get.return_value = {'status': 'stopped', 'exitstatus': 'OK'}

        svc, sn, pb, gw = self._setup_internal_service()
        # Never-synced domain route: no npm_proxy_host_id.
        dr = DomainRoute.objects.create(service=svc, domain='app.example.com', forward_port=80)

        from ..tasks import cancel_service
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

        from ..tasks.maintenance import finalize_service_network_release
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

        from ..tasks import cleanup_orphaned_ips
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

        from ..tasks import cleanup_orphaned_ips
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

        from ..tasks import delete_npm_stream
        delete_npm_stream(1, 42)  # must not raise

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_stream_connection_error_propagates(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_stream.side_effect = requests.exceptions.ConnectionError('boom')
        mock_get_client.return_value = client

        from ..tasks import delete_npm_stream
        with self.assertRaises(requests.exceptions.ConnectionError):
            delete_npm_stream(1, 42)

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_stream_npm_5xx_raises_transient_error(self, mock_pg, mock_get_client):
        from ..tasks.npm import NPMTransientError

        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_stream.side_effect = self._http_error(503)
        mock_get_client.return_value = client

        from ..tasks import delete_npm_stream
        with self.assertRaises(NPMTransientError):
            delete_npm_stream(1, 42)

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_stream_permanent_4xx_raises_http_error(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_stream.side_effect = self._http_error(400)
        mock_get_client.return_value = client

        from ..tasks import delete_npm_stream
        with self.assertRaises(requests.exceptions.HTTPError):
            delete_npm_stream(1, 42)

    def test_delete_stream_autoretry_configured_for_transient_failures(self):
        from ..tasks.npm import NPMTransientError, delete_npm_stream

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

        from ..tasks import delete_npm_proxy_host
        delete_npm_proxy_host(1, 99)  # must not raise

    @patch('inveterate.tasks.npm._get_npm_client')
    @patch('inveterate.tasks.npm.PortGateway')
    def test_delete_proxy_host_timeout_propagates(self, mock_pg, mock_get_client):
        mock_pg.objects.get.return_value = MagicMock(pk=1)
        client = MagicMock()
        client.delete_proxy_host.side_effect = requests.exceptions.Timeout('slow')
        mock_get_client.return_value = client

        from ..tasks import delete_npm_proxy_host
        with self.assertRaises(requests.exceptions.Timeout):
            delete_npm_proxy_host(1, 99)


# ===================================================================
# TestProxmoxHelpers
# ===================================================================

