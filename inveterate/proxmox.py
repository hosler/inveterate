"""
Proxmox connection and console access utilities.

Centralises the ProxmoxAPI connection pattern and console-user management
that was previously duplicated across viewsets, views, and tasks.
"""
import logging
import re
import secrets
import threading
import time

import requests
import urllib3
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

# Suppress InsecureRequestWarning for Proxmox connections with verify_ssl=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

CONSOLE_USER_PREFIX = 'inv-s'
CONSOLE_USER_REALM = 'pve'

# Legacy prefix used before per-service naming was introduced.
_LEGACY_PREFIX = 'inveterate'


class ProxmoxConsoleError(Exception):
    """Wrapper for Proxmox connection / API errors during console operations."""


def get_proxmox_connection(cluster, timeout=30):
    """Return a ``ProxmoxAPI`` handle for *cluster* (a ``Cluster`` model instance)."""
    return ProxmoxAPI(
        cluster.host,
        user=cluster.user,
        token_name='inveterate',
        token_value=cluster.key,
        verify_ssl=getattr(cluster, 'verify_ssl', False),
        port=8006,
        timeout=timeout,
    )


def console_username(service):
    """Return the Proxmox userid for console access to *service*."""
    return f'{CONSOLE_USER_PREFIX}{service.id}@{CONSOLE_USER_REALM}'


def generate_console_password():
    """Return a 24-char URL-safe password (no punctuation that could break Proxmox auth)."""
    return secrets.token_urlsafe(18)


# How long a freshly-issued set of console credentials stays valid for reuse.
# This covers the multi-step credential fetch the frontend performs (console
# creds -> Proxmox auth ticket -> termproxy -> websocket), so that a second
# ensure_console_user() call arriving while the first is still in flight (or
# just after) reuses the same Proxmox user/password instead of deleting and
# recreating the user underneath the first call's in-flight ticket.
_CONSOLE_CRED_TTL = 30  # seconds

# service.id -> (userid, password, expires_at) for the most recently issued
# console credentials. Entries are overwritten in place per service, so this
# stays bounded by the number of distinct services, not the call volume.
_console_cred_cache = {}

# service.id -> threading.Lock, serializing ensure_console_user() calls for
# the same service so a losing concurrent call waits for the winner instead
# of racing it with its own delete/recreate.
_console_cred_locks = {}
_console_cred_locks_guard = threading.Lock()


def _get_service_lock(service_id):
    with _console_cred_locks_guard:
        lock = _console_cred_locks.get(service_id)
        if lock is None:
            lock = threading.Lock()
            _console_cred_locks[service_id] = lock
        return lock


def _reset_console_cred_cache():
    """Test helper: clear cached console credentials and locks."""
    _console_cred_cache.clear()
    _console_cred_locks.clear()


def ensure_console_user(proxmox, service, machine_id):
    """Create or update a Proxmox console user for *service*.

    Serialized per-service and cached for ``_CONSOLE_CRED_TTL`` seconds: a
    concurrent or fast-repeat call (e.g. the user hitting "Reconnect" while
    the previous attempt's credential fetch is still in flight) waits on the
    per-service lock and then reuses the winner's just-issued credentials
    rather than deleting and recreating the Proxmox user again, which would
    invalidate any ticket already obtained with the old password. API tokens
    cannot change an existing user's password, so once the cache entry
    expires we still delete-then-recreate to rotate the password.

    Returns ``(userid, password)``.
    Raises ``ProxmoxConsoleError`` on Proxmox failures.
    """
    userid = console_username(service)

    lock = _get_service_lock(service.id)
    with lock:
        now = time.monotonic()
        cached = _console_cred_cache.get(service.id)
        if cached and cached[2] > now:
            return cached[0], cached[1]

        password = generate_console_password()

        try:
            try:
                proxmox.access.users.post(userid=userid, password=password)
            except ResourceException as e:
                if 'already exists' in str(e):
                    # API tokens cannot change passwords, so delete and recreate
                    proxmox.access.users(userid).delete()
                    proxmox.access.users.post(userid=userid, password=password)
                else:
                    raise

            proxmox.access.acl.put(
                path=f'/vms/{machine_id}',
                roles=['PVEVMUser'],
                users=[userid],
            )
        except (ResourceException, ConnectionError) as e:
            raise ProxmoxConsoleError(str(e)) from e

        _console_cred_cache[service.id] = (userid, password, now + _CONSOLE_CRED_TTL)
        return userid, password


def get_console_ticket(cluster_host, userid, password, verify_ssl=False):
    """Authenticate to Proxmox and return ``{ticket, CSRFPreventionToken}``.

    Raises ``ProxmoxConsoleError`` on auth failure or connection error.
    """
    try:
        resp = requests.post(
            f'https://{cluster_host}:8006/api2/json/access/ticket',
            data={'username': userid, 'password': password},
            verify=verify_ssl,
        )
    except (ConnectionError, requests.RequestException) as e:
        raise ProxmoxConsoleError(str(e)) from e

    if resp.status_code != 200:
        raise ProxmoxConsoleError('Proxmox authentication failed')

    data = resp.json()['data']
    return {
        'ticket': data['ticket'],
        'CSRFPreventionToken': data['CSRFPreventionToken'],
    }


_PER_SERVICE_RE = re.compile(
    rf'^{re.escape(CONSOLE_USER_PREFIX)}(\d+)@{re.escape(CONSOLE_USER_REALM)}$'
)


def is_console_user(userid):
    """Parse a per-service console userid and return the service id, or ``None``."""
    m = _PER_SERVICE_RE.match(userid)
    return int(m.group(1)) if m else None


_LEGACY_RE = re.compile(
    rf'^{re.escape(_LEGACY_PREFIX)}(\d+)@{re.escape(CONSOLE_USER_REALM)}$'
)


def guest_agent_resize(cluster, node_name, vmid, cols, rows):
    """Resize the guest terminal via QEMU Guest Agent exec.

    Runs ``stty`` on ``/dev/ttyS0`` and sends ``SIGWINCH`` to processes on that
    tty so the shell picks up the new dimensions immediately.

    Returns ``True`` on success, ``False`` if the guest agent is unavailable or
    the command fails (fire-and-forget).
    """
    try:
        proxmox = get_proxmox_connection(cluster, timeout=10)
        node = proxmox.nodes(node_name)
        node.qemu(vmid).agent("exec").post(
            command="/bin/sh",
            **{"input-data": f"stty -F /dev/ttyS0 cols {cols} rows {rows}\npkill -WINCH -t ttyS0\n"},
        )
        return True
    except Exception:
        logger.debug("Guest agent resize failed for VM %s on %s", vmid, node_name)
        return False


def is_legacy_console_user(userid):
    """Parse a legacy ``inveterate{owner_id}@pve`` userid and return the owner id, or ``None``."""
    m = _LEGACY_RE.match(userid)
    return int(m.group(1)) if m else None
