"""
WebSocket consumers for Inveterate console proxy.

ConsoleProxyConsumer bridges a browser xterm.js WebSocket to the Proxmox
VNC/terminal WebSocket, avoiding CORS and self-signed certificate issues.

Proxmox termproxy protocol (after auth):
  Client → Server:
    "0:<byte_length>:<data>"  – terminal input
    "1:<cols>:<rows>:"        – resize
  Server → Client:
    raw terminal output bytes
    "2"                       – keepalive ping (every ~30 s)
"""
import asyncio
import json
import logging
import ssl
from urllib.parse import quote

try:
    import websockets
    from channels.db import database_sync_to_async
    from channels.generic.websocket import AsyncWebsocketConsumer
except ImportError as exc:
    raise ImportError(
        "WebSocket support requires extra dependencies. "
        "Install them with: pip install django-inveterate[websocket]"
    ) from exc

logger = logging.getLogger(__name__)

# Timeout (seconds) waiting for Proxmox "OK" after sending auth.
_AUTH_OK_TIMEOUT = 10


class ConsoleProxyConsumer(AsyncWebsocketConsumer):
    """Bidirectional proxy between browser and Proxmox console WebSocket."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxmox_ws = None
        self.proxy_task = None
        self.authenticated = False
        self.service = None

    async def connect(self):
        self.service_id = int(self.scope['url_route']['kwargs']['service_id'])
        user = self.scope.get('user')

        if not user or user.is_anonymous:
            await self.close(code=4001)
            return

        service = await self.get_service(self.service_id)
        if service is None:
            await self.close(code=4004)
            return

        owner_id = await self.get_service_owner_id(service)
        is_staff = await database_sync_to_async(lambda: user.is_staff)()
        if not is_staff and owner_id != user.id:
            await self.close(code=4004)
            return

        self.service = service
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        if not self.authenticated:
            # First message must be JSON auth payload
            if text_data is None:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Auth message must be JSON text',
                }))
                return
            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON',
                }))
                return

            if data.get('type') != 'auth':
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'First message must have type "auth"',
                }))
                return

            required = ('ticket', 'csrf', 'username', 'port', 'vncticket')
            missing = [k for k in required if k not in data]
            if missing:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Missing fields: {", ".join(missing)}',
                }))
                return

            await self.handle_auth(data)
            return

        # After auth, translate client JSON to Proxmox termproxy protocol.
        if text_data is not None:
            try:
                msg = json.loads(text_data)
            except (json.JSONDecodeError, TypeError):
                msg = None

            try:
                if msg and msg.get('type') == 'resize':
                    cols = int(msg.get('cols', 80))
                    rows = int(msg.get('rows', 24))
                    await self.proxmox_ws.send(f"1:{cols}:{rows}:")
                elif msg and msg.get('type') == 'input':
                    payload = msg.get('data', '')
                    byte_len = len(payload.encode('utf-8'))
                    await self.proxmox_ws.send(f"0:{byte_len}:{payload}")
                else:
                    # Forward raw text as-is (fallback)
                    await self.proxmox_ws.send(text_data)
            except websockets.exceptions.ConnectionClosed:
                await self.close()
        elif bytes_data is not None:
            try:
                await self.proxmox_ws.send(bytes_data)
            except websockets.exceptions.ConnectionClosed:
                await self.close()

    async def handle_auth(self, data):
        """Establish upstream connection to Proxmox VNC WebSocket."""
        details = await self.get_service_details(self.service)
        host = details['host']
        node = details['node']
        vmtype = details['vmtype']
        vmid = details['vmid']

        port = data['port']
        vncticket = quote(data['vncticket'], safe='')

        ws_url = (
            f"wss://{host}:8006/api2/json/nodes/{node}/{vmtype}/{vmid}"
            f"/vncwebsocket?port={port}&vncticket={vncticket}"
        )

        # Allow self-signed certs
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        cookie = f"PVEAuthCookie={quote(data['ticket'], safe='')}"
        headers = {
            'Cookie': cookie,
            'CSRFPreventionToken': data['csrf'],
        }

        try:
            self.proxmox_ws = await websockets.connect(
                ws_url,
                ssl=ssl_context,
                additional_headers=headers,
                subprotocols=[websockets.Subprotocol('binary')],
            )
        except Exception as e:
            logger.warning("Proxmox WS connect failed for service %s: %s", self.service_id, e)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to connect to Proxmox console',
            }))
            await self.close()
            return

        # Send auth string: "username:ticket\n"
        auth_string = f"{data['username']}:{data['ticket']}\n"
        try:
            await self.proxmox_ws.send(auth_string)
        except websockets.exceptions.ConnectionClosed:
            await self._send_error('Proxmox closed connection during auth')
            await self.close()
            return

        # Wait for "OK" response from Proxmox before marking as ready.
        try:
            ok_msg = await asyncio.wait_for(
                self.proxmox_ws.recv(), timeout=_AUTH_OK_TIMEOUT,
            )
            ok_text = ok_msg.decode('utf-8') if isinstance(ok_msg, bytes) else ok_msg
            if ok_text != 'OK':
                logger.warning(
                    "Proxmox auth for service %s returned %r (expected 'OK')",
                    self.service_id, ok_text,
                )
                await self._send_error('Proxmox authentication failed')
                await self.close()
                return
        except asyncio.TimeoutError:
            logger.warning("Proxmox auth timeout for service %s", self.service_id)
            await self._send_error('Proxmox authentication timed out')
            await self.close()
            return
        except websockets.exceptions.ConnectionClosed:
            await self._send_error('Proxmox closed connection during auth')
            await self.close()
            return

        self.authenticated = True
        await self.send(text_data=json.dumps({'type': 'ready'}))

        # Start proxying from Proxmox → client
        self.proxy_task = asyncio.ensure_future(self.proxy_from_proxmox())

    async def proxy_from_proxmox(self):
        """Forward messages from Proxmox WebSocket to the browser client.

        Proxmox sends terminal output as binary WebSocket frames.
        We decode to text so the browser receives string data that
        xterm.js can render directly.
        """
        try:
            async for message in self.proxmox_ws:
                if isinstance(message, bytes):
                    text = message.decode('utf-8', errors='replace')
                else:
                    text = message
                # '2' is a keepalive ping from Proxmox — don't forward
                if text == '2':
                    continue
                await self.send(text_data=text)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.warning("Proxmox proxy error for service %s: %s", self.service_id, e)
        finally:
            await self.close()

    async def disconnect(self, code):
        if self.proxy_task and not self.proxy_task.done():
            self.proxy_task.cancel()
            try:
                await self.proxy_task
            except (asyncio.CancelledError, Exception):
                pass
        if self.proxmox_ws:
            try:
                await self.proxmox_ws.close()
            except Exception:
                pass
            self.proxmox_ws = None

    async def _send_error(self, message):
        """Send a JSON error message to the client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
        }))

    @database_sync_to_async
    def get_service(self, service_id):
        from .models import Service
        try:
            return Service.objects.select_related(
                'node__cluster', 'service_plan', 'owner',
            ).get(id=service_id)
        except Service.DoesNotExist:
            return None

    @database_sync_to_async
    def get_service_owner_id(self, service):
        return service.owner_id

    @database_sync_to_async
    def get_service_details(self, service):
        vmtype = "lxc" if service.service_plan.type == "lxc" else "qemu"
        return {
            'host': service.node.cluster.host,
            'node': service.node.name,
            'vmid': service.machine_id,
            'vmtype': vmtype,
        }
