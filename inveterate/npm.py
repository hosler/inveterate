import logging

import requests

logger = logging.getLogger(__name__)


class NPMClient:
    """Thin wrapper around the Nginx Proxy Manager REST API."""

    def __init__(self, host, admin_email, admin_password):
        self.host = host.rstrip('/')
        self.admin_email = admin_email
        self.admin_password = admin_password
        self._token = None

    def _authenticate(self):
        resp = requests.post(
            f'{self.host}/api/tokens',
            json={'identity': self.admin_email, 'secret': self.admin_password},
            timeout=15,
        )
        resp.raise_for_status()
        self._token = resp.json()['token']

    def _headers(self):
        if not self._token:
            self._authenticate()
        return {'Authorization': f'Bearer {self._token}'}

    def _request(self, method, path, **kwargs):
        kwargs.setdefault('timeout', 30)
        url = f'{self.host}{path}'
        resp = getattr(requests, method)(url, headers=self._headers(), **kwargs)
        if resp.status_code == 401:
            self._authenticate()
            resp = getattr(requests, method)(url, headers=self._headers(), **kwargs)
        resp.raise_for_status()
        return resp

    # --- Streams (PortForward) ---

    def create_stream(self, incoming_port, forwarding_host, forwarding_port, tcp=True, udp=False):
        payload = {
            'incoming_port': incoming_port,
            'forwarding_host': forwarding_host,
            'forwarding_port': forwarding_port,
            'tcp_forwarding': tcp,
            'udp_forwarding': udp,
        }
        resp = self._request('post', '/api/nginx/streams', json=payload)
        return resp.json()

    def update_stream(self, stream_id, **fields):
        resp = self._request('put', f'/api/nginx/streams/{stream_id}', json=fields)
        return resp.json()

    def delete_stream(self, stream_id):
        self._request('delete', f'/api/nginx/streams/{stream_id}')

    def enable_stream(self, stream_id):
        return self.update_stream(stream_id, enabled=True)

    def disable_stream(self, stream_id):
        return self.update_stream(stream_id, enabled=False)

    # --- Proxy Hosts (DomainRoute) ---

    def create_proxy_host(self, domain, forward_host, forward_port, ssl=True, force_ssl=True):
        payload = {
            'domain_names': [domain],
            'forward_host': forward_host,
            'forward_port': forward_port,
            'forward_scheme': 'http',
            'ssl_forced': force_ssl,
            'block_exploits': True,
            'allow_websocket_upgrade': True,
        }
        if ssl:
            payload['certificate_id'] = 'new'
            payload['meta'] = {
                'letsencrypt_agree': True,
                'letsencrypt_email': self.admin_email,
                'dns_challenge': False,
            }
        resp = self._request('post', '/api/nginx/proxy-hosts', json=payload)
        return resp.json()

    def update_proxy_host(self, proxy_host_id, **fields):
        resp = self._request('put', f'/api/nginx/proxy-hosts/{proxy_host_id}', json=fields)
        return resp.json()

    def delete_proxy_host(self, proxy_host_id):
        self._request('delete', f'/api/nginx/proxy-hosts/{proxy_host_id}')
