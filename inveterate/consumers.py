"""
WebSocket consumers for Inveterate console proxy.

ConsoleProxyConsumer bridges a browser xterm.js WebSocket to the Proxmox
VNC/terminal WebSocket, avoiding CORS and self-signed certificate issues.
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

        # After auth, forward raw data to Proxmox
        if text_data is not None:
            try:
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
            )
        except Exception as e:
            logger.warning("Proxmox WS connect failed for service %s: %s", self.service_id, e)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to connect to Proxmox console',
            }))
            await self.close()
            return

        # Send initial auth string
        auth_string = f"{data['username']}:{data['ticket']}\n"
        try:
            await self.proxmox_ws.send(auth_string)
        except websockets.exceptions.ConnectionClosed:
            await self.close()
            return

        self.authenticated = True
        await self.send(text_data=json.dumps({'type': 'ready'}))

        # Start proxying from Proxmox → client
        self.proxy_task = asyncio.ensure_future(self.proxy_from_proxmox())

    async def proxy_from_proxmox(self):
        """Forward messages from Proxmox WebSocket to the browser client."""
        try:
            async for message in self.proxmox_ws:
                if isinstance(message, bytes):
                    await self.send(bytes_data=message)
                else:
                    await self.send(text_data=message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.warning("Proxmox proxy error for service %s: %s", self.service_id, e)
        finally:
            await self.close()

    async def disconnect(self, code):
        if self.proxy_task and not self.proxy_task.done():
            self.proxy_task.cancel()
        if self.proxmox_ws:
            await self.proxmox_ws.close()

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
