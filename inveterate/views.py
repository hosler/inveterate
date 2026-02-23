"""
Template views for Inveterate web interface.
Serves HTML pages that interact with the REST API via JavaScript.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import json

from .models import Service


# Authentication Views
class LoginView(auth_views.LoginView):
    template_name = 'auth/login.html'
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = 'login'


# Dashboard Views
class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin dashboard with system stats"""
    template_name = 'dashboard/index.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


# Service Views
class ServiceListView(LoginRequiredMixin, TemplateView):
    """List user's services"""
    template_name = 'services/list.html'
    login_url = '/login/'


class ServiceDetailView(LoginRequiredMixin, TemplateView):
    """Service detail and control panel"""
    template_name = 'services/detail.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_id'] = kwargs.get('service_id')
        return context


class ServiceConsoleView(LoginRequiredMixin, TemplateView):
    """Service console access page"""
    template_name = 'services/console.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_id'] = kwargs.get('service_id')
        return context


# Cluster & Node Views (Admin Only)
class ClusterListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """List clusters (admin only)"""
    template_name = 'dashboard/clusters.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


class NodeListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """List nodes (admin only)"""
    template_name = 'dashboard/nodes.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


# Service Order View (any authenticated user)
class ServiceOrderView(LoginRequiredMixin, TemplateView):
    """Multi-step service ordering wizard"""
    template_name = 'services/order.html'
    login_url = '/login/'


# Admin Management Views
class AdminServiceListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin view of all services"""
    template_name = 'dashboard/services.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


class PlanListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Manage plans"""
    template_name = 'dashboard/plans.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


class TemplateListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Manage templates"""
    template_name = 'dashboard/templates.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


class AppProfileListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Manage app profiles"""
    template_name = 'dashboard/apps.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


class IPPoolListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """View IP pool statistics"""
    template_name = 'dashboard/ips.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_staff


# Simple function-based views
@login_required
def home_view(request):
    """Redirect to appropriate landing page based on user role"""
    if request.user.is_staff:
        return redirect('dashboard')
    return redirect('services')


# Console Proxy Views
@login_required
def console_auth_view(request, service_id):
    """
    Authenticate with Proxmox and return ticket for console access.
    This endpoint is called by the frontend to get Proxmox credentials.
    """
    service = get_object_or_404(Service, id=service_id)

    # Verify user owns this service or is admin
    if not request.user.is_staff and service.owner != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    if not service.machine_id:
        return JsonResponse({'error': 'No machine provisioned'}, status=400)

    # Get console credentials from the API viewset logic
    from .viewsets.service import ServiceViewSet
    import random
    import string
    from proxmoxer import ProxmoxAPI
    from proxmoxer.core import ResourceException

    try:
        proxmox_user = f'inveterate{service.owner_id}'
        password = ''.join(
            random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation)
            for _ in range(10)
        )

        proxmox = ProxmoxAPI(
            service.node.cluster.host,
            user=service.node.cluster.user,
            token_name='inveterate',
            token_value=service.node.cluster.key,
            verify_ssl=False,
            port=8006
        )

        # Create or reset console user
        try:
            proxmox.access.users.post(userid=f"{proxmox_user}@pve", password=password)
        except ResourceException as e:
            if "already exists" in str(e):
                proxmox.access.users(f"{proxmox_user}@pve").delete()
                proxmox.access.users.post(userid=f"{proxmox_user}@pve", password=password)

        # Set ACL permissions
        proxmox.access.acl.put(
            path=f"/vms/{service.machine_id}",
            roles=["PVEVMUser"],
            users=[f"{proxmox_user}@pve"]
        )

        # Authenticate to get ticket
        auth_response = requests.post(
            f"https://{service.node.cluster.host}:8006/api2/json/access/ticket",
            data={
                'username': f"{proxmox_user}@pve",
                'password': password
            },
            verify=False
        )

        if auth_response.status_code == 200:
            auth_data = auth_response.json()['data']
            vm_type = "lxc" if service.service_plan.type == "lxc" else "qemu"

            return JsonResponse({
                'success': True,
                'ticket': auth_data['ticket'],
                'CSRFPreventionToken': auth_data['CSRFPreventionToken'],
                'username': f"{proxmox_user}@pve",
                'node': service.node.name,
                'vmid': service.machine_id,
                'vmtype': vm_type,
                'host': service.node.cluster.host
            })
        else:
            return JsonResponse({'error': 'Authentication failed'}, status=401)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
def console_proxy_view(request, service_id):
    """
    Proxy requests to Proxmox console API.
    This handles the WebSocket upgrade for xterm.js connection.
    """
    service = get_object_or_404(Service, id=service_id)

    # Verify user owns this service or is admin
    if not request.user.is_staff and service.owner != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    # Get Proxmox details from request
    ticket = request.GET.get('ticket')
    csrf_token = request.GET.get('csrf')

    if not ticket or not csrf_token:
        return JsonResponse({'error': 'Missing authentication'}, status=400)

    vm_type = "lxc" if service.service_plan.type == "lxc" else "qemu"
    proxmox_host = service.node.cluster.host

    # Construct Proxmox console websocket URL
    ws_url = f"wss://{proxmox_host}:8006/api2/json/nodes/{service.node.name}/{vm_type}/{service.machine_id}/vncwebsocket"

    return JsonResponse({
        'websocket_url': ws_url,
        'node': service.node.name,
        'vmid': service.machine_id,
        'vmtype': vm_type
    })
