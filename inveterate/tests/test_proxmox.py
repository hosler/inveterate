from .helpers import *  # noqa: F401,F403
from .helpers import (  # noqa: F401
    _admin, _app_profile, _cluster, _disk, _internal_pool, _ip_pool, _node,
    _plan, _port_gateway, _service, _service_plan, _template, _txt_answer, _user,
)

class TestProxmoxHelpers(TestCase):
    """Unit tests for inveterate.proxmox utility functions."""

    def setUp(self):
        from ..proxmox import _reset_console_cred_cache
        _reset_console_cred_cache()

    def test_console_username_format(self):
        from ..proxmox import console_username
        svc = MagicMock(id=42)
        self.assertEqual(console_username(svc), 'inv-s42@pve')

    def test_console_username_large_id(self):
        from ..proxmox import console_username
        svc = MagicMock(id=1000123)
        self.assertEqual(console_username(svc), 'inv-s1000123@pve')

    def test_generate_console_password_length_and_safety(self):
        from ..proxmox import generate_console_password
        pw = generate_console_password()
        self.assertEqual(len(pw), 24)
        # URL-safe means only alphanumeric, hyphen, underscore
        import re
        self.assertRegex(pw, r'^[A-Za-z0-9_-]+$')

    def test_ensure_console_user_creates_new(self):
        from ..proxmox import ensure_console_user
        proxmox = MagicMock()
        svc = MagicMock(id=7)
        userid, password = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid, 'inv-s7@pve')
        self.assertTrue(len(password) > 0)
        proxmox.access.users.post.assert_called_once()
        proxmox.access.acl.put.assert_called_once_with(
            path='/vms/1000007', roles=['PVEVMUser'], users=['inv-s7@pve'],
        )

    def test_ensure_console_user_updates_existing(self):
        from ..proxmox import ensure_console_user
        from proxmoxer.core import ResourceException

        proxmox = MagicMock()
        # First post raises "already exists", second post (after delete) succeeds
        proxmox.access.users.post.side_effect = [
            ResourceException(
                status_code=500, status_message='',
                content='user already exists', errors=None,
            ),
            None,  # second call succeeds
        ]
        svc = MagicMock(id=7)
        userid, password = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid, 'inv-s7@pve')
        proxmox.access.users('inv-s7@pve').delete.assert_called_once()
        self.assertEqual(proxmox.access.users.post.call_count, 2)
        proxmox.access.acl.put.assert_called_once()

    def test_ensure_console_user_repeat_call_reuses_cached_credentials(self):
        """A second call for the same service shortly after the first (e.g. a
        racing "Reconnect" click during the in-flight credential fetch) must
        return the exact same userid/password and must not touch Proxmox
        again, since deleting/recreating the user would invalidate a ticket
        already obtained with the first password."""
        from ..proxmox import ensure_console_user
        proxmox = MagicMock()
        svc = MagicMock(id=7)

        userid1, password1 = ensure_console_user(proxmox, svc, 1000007)
        userid2, password2 = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid1, userid2)
        self.assertEqual(password1, password2)
        proxmox.access.users.post.assert_called_once()
        proxmox.access.acl.put.assert_called_once()

    def test_ensure_console_user_rotates_after_cache_expires(self):
        """Once the cached credentials expire, the next call rotates the
        password (still hitting Proxmox), so passwords aren't cached forever."""
        from ..proxmox import ensure_console_user
        proxmox = MagicMock()
        svc = MagicMock(id=7)

        with patch('inveterate.proxmox.time.monotonic', return_value=1000.0):
            userid1, password1 = ensure_console_user(proxmox, svc, 1000007)

        with patch('inveterate.proxmox.time.monotonic', return_value=1000.0 + 3600):
            userid2, password2 = ensure_console_user(proxmox, svc, 1000007)

        self.assertEqual(userid1, userid2)
        self.assertNotEqual(password1, password2)
        self.assertEqual(proxmox.access.users.post.call_count, 2)

    def test_ensure_console_user_reraises_other_error(self):
        from ..proxmox import ensure_console_user, ProxmoxConsoleError
        from proxmoxer.core import ResourceException

        proxmox = MagicMock()
        proxmox.access.users.post.side_effect = ResourceException(
            status_code=500, status_message='',
            content='something else went wrong', errors=None,
        )
        svc = MagicMock(id=7)
        with self.assertRaises(ProxmoxConsoleError):
            ensure_console_user(proxmox, svc, 1000007)

    def test_ensure_console_user_handles_connection_error(self):
        from ..proxmox import ensure_console_user, ProxmoxConsoleError

        proxmox = MagicMock()
        proxmox.access.users.post.side_effect = ConnectionError('refused')
        svc = MagicMock(id=7)
        with self.assertRaises(ProxmoxConsoleError):
            ensure_console_user(proxmox, svc, 1000007)

    @patch('inveterate.proxmox.requests.post')
    def test_get_console_ticket_success(self, mock_post):
        from ..proxmox import get_console_ticket
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'data': {
                'ticket': 'PVE:ticket123',
                'CSRFPreventionToken': 'csrf-tok',
            }},
        )
        result = get_console_ticket('10.0.0.1', 'inv-s7@pve', 'pass')
        self.assertEqual(result['ticket'], 'PVE:ticket123')
        self.assertEqual(result['CSRFPreventionToken'], 'csrf-tok')

    @patch('inveterate.proxmox.requests.post')
    def test_get_console_ticket_auth_failure(self, mock_post):
        from ..proxmox import get_console_ticket, ProxmoxConsoleError
        mock_post.return_value = MagicMock(status_code=401)
        with self.assertRaises(ProxmoxConsoleError):
            get_console_ticket('10.0.0.1', 'inv-s7@pve', 'badpass')

    def test_is_console_user_valid(self):
        from ..proxmox import is_console_user
        self.assertEqual(is_console_user('inv-s42@pve'), 42)

    def test_is_console_user_invalid(self):
        from ..proxmox import is_console_user
        self.assertIsNone(is_console_user('root@pam'))
        self.assertIsNone(is_console_user('inv-sABC@pve'))
        self.assertIsNone(is_console_user(''))

    def test_is_console_user_legacy_returns_none(self):
        from ..proxmox import is_console_user
        self.assertIsNone(is_console_user('inveterate5@pve'))

    def test_is_legacy_console_user(self):
        from ..proxmox import is_legacy_console_user
        self.assertEqual(is_legacy_console_user('inveterate5@pve'), 5)
        self.assertIsNone(is_legacy_console_user('inv-s5@pve'))
        self.assertIsNone(is_legacy_console_user('root@pam'))

    def test_get_proxmox_connection(self):
        from ..proxmox import get_proxmox_connection
        cluster = MagicMock(host='10.0.0.1', user='root@pam', key='tok', verify_ssl=False)
        with patch('inveterate.proxmox.ProxmoxAPI') as mock_cls:
            get_proxmox_connection(cluster, timeout=60)
            mock_cls.assert_called_once_with(
                '10.0.0.1', user='root@pam', token_name='inveterate',
                token_value='tok', verify_ssl=False, port=8006, timeout=60,
            )


# ===================================================================
# TestConsoleErrorHandling
# ===================================================================

