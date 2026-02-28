"""
Proxmox connection and console access utilities.

Centralises the ProxmoxAPI connection pattern and console-user management
that was previously duplicated across viewsets, views, and tasks.
"""
import logging
import re
import secrets

import requests
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError

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


def ensure_console_user(proxmox, service, machine_id):
    """Create or update a Proxmox console user for *service*.

    Uses PUT to update the password on an existing user rather than
    delete-then-recreate, which avoids a window where the user doesn't exist.

    Returns ``(userid, password)``.
    Raises ``ProxmoxConsoleError`` on Proxmox failures.
    """
    userid = console_username(service)
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


def is_legacy_console_user(userid):
    """Parse a legacy ``inveterate{owner_id}@pve`` userid and return the owner id, or ``None``."""
    m = _LEGACY_RE.match(userid)
    return int(m.group(1)) if m else None
