from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from ..proxmox import get_proxmox_connection, ensure_console_user, ProxmoxConsoleError
from ..task_ownership import record_task_owner


class ServiceActionThrottle(ScopedRateThrottle):
    scope = 'service_action'


class ConsoleThrottle(ScopedRateThrottle):
    scope = 'console'

from .base import DynamicPageModelViewSet, MultiSerializerViewSetMixin
from .. import models
from .. import serializers
from ..tasks import (
    provision_service,
    cancel_service,
    start_vm,
    stop_vm,
    reboot_vm,
    reset_vm,
    reset_vm_password,
    shutdown_vm,
    get_vm_status,
    get_vm_ips,
    get_vm_osinfo,
    update_service_ssh_keys,
)

UserModel = get_user_model()


class ServicePlanViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | IsAuthenticated]
    throttle_scope = 'authenticated'
    filterset_fields = ['type']
    search_fields = ['name']
    ordering_fields = ['id', 'name', 'created']

    default_serializer_class = serializers.ServicePlanSerializer
    admin_serializer_action_classes = {
        'list': serializers.ServicePlanSerializer,
        'retrieve': serializers.ServicePlanSerializer,
        'update': serializers.ServicePlanSerializer,
        'create': serializers.ServicePlanSerializer,
        'metadata': serializers.ServicePlanSerializer,
    }
    serializer_action_classes = {
        'list': serializers.ServicePlanSerializerClient,
        'retrieve': serializers.ServicePlanSerializerClient,
        'update': serializers.ServicePlanSerializerClient,
        'create': serializers.ServicePlanSerializerClient,
        'metadata': serializers.ServicePlanSerializerClient,
    }

    def get_queryset(self):
        if self.request.user.is_staff:
            return models.ServicePlan.objects.all().exclude(service__status='destroyed').order_by('pk')
        return models.ServicePlan.objects.filter(service__owner=self.request.user).exclude(
            service__status='destroyed').order_by('pk')


class ServiceViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | IsAuthenticated]
    throttle_scope = 'authenticated'
    filterset_fields = ['status', 'node', 'owner']
    search_fields = ['hostname']
    ordering_fields = ['id', 'hostname', 'status', 'created']

    default_serializer_class = serializers.ServiceSerializer
    admin_serializer_action_classes = {
        'list': serializers.ServiceSerializer,
        'retrieve': serializers.ServiceSerializer,
        'update': serializers.ServiceSerializer,
        'create': serializers.ServiceSerializer,
        'metadata': serializers.ServiceSerializer,
    }
    serializer_action_classes = {
        'list': serializers.ServiceSerializerClient,
        'retrieve': serializers.ServiceSerializerClient,
        'update': serializers.ServiceSerializerClient,
        'create': serializers.ServiceSerializerClient,
        'metadata': serializers.ServiceSerializerClient,
    }

    def _guarded_dispatch(self, service, task, *args, **kwargs):
        """Serialize mutating operations on a service.

        Atomically claim the service's operation lock (compare-and-set on
        ``operation_in_progress``) before enqueueing ``task``. Returns HTTP 409
        if an operation is already in progress. The flag is set True here — right
        before ``.delay()`` — so a rapid second request sees it; the Celery task
        clears it False in its finally block. If dispatch itself fails we clear
        the flag so the service isn't left permanently locked.
        """
        claimed = models.Service.objects.filter(
            pk=service.pk, operation_in_progress=False,
        ).update(operation_in_progress=True)
        if not claimed:
            return Response(
                {"detail": "An operation is already in progress for this service."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            task_result = task.delay(*args, **kwargs)
        except Exception:
            models.Service.objects.filter(pk=service.pk).update(operation_in_progress=False)
            raise
        record_task_owner(task_result.id, self.request.user)
        return Response({"task_id": task_result.id}, status=202)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def start(self, request, pk=None):
        service = self.get_object()
        return self._guarded_dispatch(service, start_vm, service.pk)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def shutdown(self, request, pk=None):
        service = self.get_object()
        return self._guarded_dispatch(service, shutdown_vm, service.pk)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def reset(self, request, pk=None):
        service = self.get_object()
        return self._guarded_dispatch(service, reset_vm, service.pk)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def stop(self, request, pk=None):
        service = self.get_object()
        return self._guarded_dispatch(service, stop_vm, service.pk)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def reboot(self, request, pk=None):
        service = self.get_object()
        return self._guarded_dispatch(service, reboot_vm, service.pk)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def status(self, request, pk=None):
        service = self.get_object()
        if not service.node:
            return Response({"detail": "Service has no node assigned."}, status=503)
        stats = get_vm_status(service.pk)
        return Response(stats)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def cancel(self, request, pk=None):
        service = self.get_object()
        return self._guarded_dispatch(service, cancel_service, service.pk)

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def provision(self, request, pk=None):
        service = self.get_object()
        # 409 if an operation is already running — this also closes the
        # double-provision-after-lock-expiry race (a rapid second POST sees the
        # flag already claimed instead of enqueueing a duplicate provision).
        return self._guarded_dispatch(service, provision_service, service_id=service.pk, password=None)

    @action(methods=['get'], detail=True)
    def ips(self, request, pk=None):
        service = self.get_object()
        ips = get_vm_ips(service.pk)
        return Response(ips)

    @action(methods=['get'], detail=True, throttle_classes=[ConsoleThrottle])
    def console(self, request, pk=None):
        """
        Get console access credentials for a service's VM.

        Creates a per-service Proxmox user (format: inv-s{service_id}@pve) with
        PVEVMUser role scoped to this specific VM. Orphaned console users are
        periodically cleaned up by the cleanup_console_users task.
        """
        service = self.get_object()
        if not service.machine_id:
            return Response({'detail': 'No machine provisioned for this service'}, status=400)

        try:
            proxmox = get_proxmox_connection(service.node.cluster)
            userid, password = ensure_console_user(proxmox, service, service.machine_id)
        except ProxmoxConsoleError as e:
            return Response({'detail': f'Console unavailable: {e}'}, status=502)

        vm_type = "lxc" if service.service_plan.type == "lxc" else "qemu"
        return Response({
            "username": userid,
            "password": password,
            "node": service.node.name,
            "machine": service.machine_id,
            "type": vm_type,
        })

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def ssh_keys(self, request, pk=None):
        """Update SSH authorized keys on a running KVM service."""
        service = self.get_object()
        ssh_keys = request.data.get('ssh_keys', [])
        if not isinstance(ssh_keys, list):
            return Response({'detail': 'ssh_keys must be a list of public key strings.'}, status=400)
        if service.service_plan.type != 'kvm':
            return Response({'detail': 'SSH key updates are only supported for KVM services.'}, status=400)
        task = update_service_ssh_keys.delay(service.id, ssh_keys)
        record_task_owner(task.id, request.user)
        return Response({'task_id': task.id}, status=202)

    @action(methods=['get'], detail=True)
    def osinfo(self, request, pk=None):
        """Get OS info from QEMU guest agent."""
        service = self.get_object()
        info = get_vm_osinfo(service.pk)
        return Response(info or {})

    @action(methods=['post'], detail=True, throttle_classes=[ServiceActionThrottle])
    def reset_password(self, request, pk=None):
        """Reset a user's password inside the guest via QEMU guest agent."""
        service = self.get_object()
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        if not username:
            return Response({'detail': 'username is required.'}, status=400)
        if len(password) < 8:
            return Response({'detail': 'password must be at least 8 characters.'}, status=400)
        if service.service_plan.type != 'kvm':
            return Response({'detail': 'Password reset is only supported for KVM services.'}, status=400)
        task = reset_vm_password.delay(service.pk, username, password)
        record_task_owner(task.id, request.user)
        return Response({'task_id': task.id}, status=202)

    @action(methods=['post'], detail=False, permission_classes=[IsAdminUser])
    def bulk_import(self, request):
        """Import multiple VMs/LXCs from Proxmox nodes"""
        vms_data = request.data.get('vms', [])
        default_owner_id = request.data.get('default_owner_id')

        if not vms_data:
            return Response({
                'success': False,
                'message': 'No VMs provided for import'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not default_owner_id:
            return Response({
                'success': False,
                'message': 'Default owner ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            default_owner = UserModel.objects.get(pk=default_owner_id)
        except UserModel.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Default owner not found'
            }, status=status.HTTP_400_BAD_REQUEST)

        imported_services = []
        errors = []

        with transaction.atomic():
            for vm_data in vms_data:
                try:
                    node_id = vm_data.get('node_id')
                    vm_id = vm_data.get('vmid')
                    vm_name = vm_data.get('name')
                    vm_type = vm_data.get('type')  # 'qemu' or 'lxc'
                    vm_status = vm_data.get('status')
                    vm_mem = vm_data.get('mem', 0)
                    vm_maxmem = vm_data.get('maxmem', 512 * 1024 * 1024)  # Default 512MB
                    vm_cpus = vm_data.get('cpus', 1)
                    vm_disk = vm_data.get('disk', 0)
                    vm_maxdisk = vm_data.get('maxdisk', 8 * 1024 * 1024 * 1024)  # Default 8GB

                    if not all([node_id, vm_id, vm_name]):
                        errors.append(f"Missing required fields for VM: {vm_data}")
                        continue

                    try:
                        node = models.Node.objects.get(pk=node_id)
                    except models.Node.DoesNotExist:
                        errors.append(f"Node {node_id} not found for VM {vm_name}")
                        continue

                    # Check if service with this machine_id already exists (any node)
                    if models.Service.objects.filter(machine_id=vm_id).exclude(status='destroyed').exists():
                        errors.append(f"VM {vm_name} (ID: {vm_id}) already imported")
                        continue

                    # Convert VM type from Proxmox format to our format
                    service_type = 'lxc' if vm_type == 'lxc' else 'kvm'

                    # Create ServicePlan with VM specifications
                    service_plan = models.ServicePlan.objects.create(
                        name=f'Imported {service_type.upper()}',
                        type=service_type,
                        # Convert bytes to appropriate units
                        size=int(vm_maxdisk / (1024**3)) if vm_maxdisk else 8,  # GB
                        ram=int(vm_maxmem / (1024**2)) if vm_maxmem else 512,   # MB
                        cores=int(vm_cpus) if vm_cpus else 1,
                        swap=int(vm_maxmem / (1024**2) / 2) if vm_maxmem else 256,  # Half of RAM
                        cpu_units=1024,  # Default
                        cpu_limit=1.00,  # Default
                        bandwidth=1024,  # Default 1Gbps
                        ipv4_ips=1,     # Default 1 IP
                        ipv6_ips=0,     # Default no IPv6
                        internal_ips=0  # Default no internal IPs
                    )

                    # Create Service
                    service = models.Service.objects.create(
                        owner=default_owner,
                        hostname=vm_name,
                        machine_id=int(vm_id),
                        node=node,
                        service_plan=service_plan,
                        status='active' if vm_status == 'running' else 'suspended'
                    )

                    imported_services.append({
                        'id': service.id,
                        'hostname': service.hostname,
                        'machine_id': service.machine_id,
                        'node': node.name,
                        'type': service_type,
                        'status': service.status
                    })

                except Exception as e:
                    errors.append(f"Error importing VM {vm_data.get('name', 'unknown')}: {str(e)}")

        return Response({
            'success': len(imported_services) > 0,
            'imported_count': len(imported_services),
            'error_count': len(errors),
            'imported_services': imported_services,
            'errors': errors
        }, status=status.HTTP_201_CREATED if imported_services else status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Use the cancel action to tear down a service.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        qs = models.Service.objects.select_related(
            'service_plan', 'node', 'node__cluster',
        ).exclude(status='destroyed').order_by('pk')
        if self.request.user.is_staff:
            return qs
        return qs.filter(owner=self.request.user)
