from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

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

        from ..tasks import cleanup_console_users
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

        from ..tasks import cleanup_console_users
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

