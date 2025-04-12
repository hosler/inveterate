from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import ReadOnlyAnonymous
from .tasks import provision_service, calculate_inventory, start_vm, stop_vm, reboot_vm, \
    reset_vm, shutdown_vm, get_vm_status, get_cluster_resources, get_vm_ips

if settings.STRIPE_LIVE_SECRET_KEY or settings.STRIPE_TEST_SECRET_KEY:
    import djstripe.settings
    import stripe
    from djstripe.models import Session, Customer, Product, Price

from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from .permissions import ReadOnly
from . import models
from . import serializers
import random
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException

UserModel = get_user_model()


class DynamicPageModelViewSet(viewsets.ModelViewSet):
    def paginate_queryset(self, queryset):
        if 'no_page' in self.request.query_params:
            return None

        return super().paginate_queryset(queryset)

    def list(self, request, *args, **kwargs):
        if request.accepted_renderer.format == 'form':
            # Per HTMLFormRenderer docs create a serializer with no object for an empty form
            serializer = self.get_serializer()
            return Response(serializer.data)
        else:
            return super().list(request, *args, **kwargs)


class MultiSerializerViewSetMixin(object):
    def get_serializer_class(self):
        try:
            user = self.request.user
        except AttributeError:
            return self.default_serializer_class
        if user.is_staff:
            action_classes = self.admin_serializer_action_classes
        else:
            action_classes = self.serializer_action_classes
        try:
            return action_classes[self.action]
        except (KeyError, AttributeError):
            return action_classes['default']


class ClusterViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.Cluster.objects.order_by('pk')
    default_serializer_class = serializers.ClusterSerializer
    admin_serializer_action_classes = {
        'list': serializers.ClusterSerializer,
        'retrieve': serializers.ClusterSerializer,
        'update': serializers.ClusterSerializer,
        'create': serializers.ClusterSerializer,
        'default': serializers.ClusterSerializer
    }
    serializer_action_classes = {}

    @action(methods=['get'], detail=True)
    def nodes(self, request, pk=None):
        stats = get_cluster_resources(pk=pk, query_type="node")
        return Response(stats, status=202)

    @action(methods=['get'], detail=True)
    def vms(self, request, pk=None):
        stats = get_cluster_resources(pk=pk, query_type="vm")
        return Response(stats, status=202)

    @action(methods=['get'], detail=True)
    def disks(self, request, pk=None):
        stats = get_cluster_resources(pk=pk, query_type="storage")
        return Response(stats, status=202)

    @action(methods=['get'], detail=False)
    def stats(self, request, pk=None):
        stats = {
            'cluster': {
                'type': 'count',
                'label': 'Clusters',
                'value': models.Cluster.objects.all().count()
            },
            'node': {
                'type': 'count',
                'label': 'Nodes',
                'value': models.Node.objects.all().count()
            },
            'service': {
                'type': 'count',
                'label': 'Services',
                'value': models.Service.objects.all().exclude(status='destroyed').count()
            }
        }
        return Response(stats, status=202)

    @action(methods=['get'], detail=False)
    def test(self, request, pk=None):
        stats = { "wat": 'hi'
        }
        return Response(stats, status=202)


class NodeViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.Node.objects.order_by('pk')
    serializer_class = serializers.NodeSerializer

    @action(methods=['get'], detail=False, description="the stats")
    def stats(self, request, pk=None):
        stats = {
            'cluster': {
                'type': 'count',
                'label': 'Clusters',
                'value': models.Cluster.objects.all().count()
            },
            'node': {
                'type': 'count',
                'label': 'Nodes',
                'value': models.Node.objects.all().count()
            },
            'service': {
                'type': 'count',
                'label': 'Services',
                'value': models.Service.objects.all().exclude(status='destroyed').count()
            }
        }
        return Response(stats, status=202)

class NodeDiskViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.NodeDisk.objects.order_by('pk')
    serializer_class = serializers.NodeDiskSerializer


class IPPoolViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.IPPool.objects.order_by('pk')
    serializer_class = serializers.IPPoolSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance:
            used_ips = models.IP.objects.filter(pool=instance, owner__isnull=False).count()
            if used_ips > 0:
                return Response(data={'message': "IPs in pool are currently in use"},
                                status=status.HTTP_400_BAD_REQUEST)
        return super(IPPoolViewSet, self).destroy(request, *args, **kwargs)


class InventoryViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | ReadOnlyAnonymous]
    queryset = models.Inventory.objects.order_by('pk')
    serializer_class = serializers.InventorySerializer

    @action(methods=['post'], detail=False)
    def calculate(self, request):
        task = calculate_inventory.delay()
        return Response({"task_id": task.id}, status=202)

class IPViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.IP.objects.order_by('pk')
    serializer_class = serializers.IPSerializer

    @action(methods=['get'], detail=False)
    def stats(self, request, pk=None):
        stats = {
            'private': {
                'type': 'count',
                'label': 'Internal IPs',
                'value': models.IP.objects.filter(pool__internal=True).count()
            },
            'ipv4': {
                'type': 'count',
                'label': 'IPv4 IPs',
                'value': models.IP.objects.filter(pool__internal=False).filter(pool__type='ipv4').count()
            },
            'ipv6': {
                'type': 'count',
                'label': 'IPv6 IPs',
                'value': models.IP.objects.filter(pool__internal=False).filter(pool__type='ipv6').count()
            }
        }
        return Response(stats, status=202)

class PlanViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | ReadOnlyAnonymous]
    queryset = models.Plan.objects.order_by('pk')
    serializer_class = serializers.PlanSerializer

    @action(methods=['get'], detail=False)
    def stats(self, request, pk=None):
        stats = {
            'plans': {
                'type': 'count',
                'label': 'Plans',
                'value': models.Plan.objects.all().count()
            }
        }
        return Response(stats, status=202)

class TemplateViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.Template.objects.order_by('pk')
    serializer_class = serializers.TemplateSerializer

    @action(methods=['get'], detail=False)
    def stats(self, request, pk=None):
        stats = {
            'templates': {
                'type': 'count',
                'label': 'KVM Plans',
                'value': models.Template.objects.all().count()
            }
        }
        return Response(stats, status=202)

class ServicePlanViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | IsAuthenticated]

    default_serializer_class = serializers.ServicePlanSerializer
    admin_serializer_action_classes = {
        'list': serializers.ServicePlanSerializer,
        'retrieve': serializers.ServicePlanSerializer,
        'update': serializers.ServicePlanSerializer,
        'create': serializers.ServicePlanSerializer,
        'default': serializers.GenericActionSerializer,
        'metadata': serializers.ServicePlanSerializer,
    }
    serializer_action_classes = {
        'list': serializers.ServicePlanSerializerClient,
        'retrieve': serializers.ServicePlanSerializerClient,
        'update': serializers.ServicePlanSerializerClient,
        'create': serializers.ServicePlanSerializerClient,
        'default': serializers.GenericActionSerializer,
        'metadata': serializers.ServicePlanSerializerClient
    }

    def get_queryset(self):
        if self.request.user.is_staff:
            return models.ServicePlan.objects.all().exclude(service__status='destroyed').order_by('pk')
        return models.ServicePlan.objects.filter(service__owner=self.request.user).exclude(
            service__status='destroyed').order_by('pk')


class ServiceViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | IsAuthenticated]

    default_serializer_class = serializers.ServiceSerializer
    admin_serializer_action_classes = {
        'list': serializers.ServiceSerializer,
        'retrieve': serializers.ServiceSerializer,
        'update': serializers.ServiceSerializer,
        'create': serializers.ServiceSerializer,
        'default': serializers.GenericActionSerializer,
        'metadata': serializers.ServiceSerializer,
    }
    serializer_action_classes = {
        'list': serializers.ServiceSerializerClient,
        'retrieve': serializers.ServiceSerializerClient,
        'update': serializers.ServiceSerializerClient,
        'create': serializers.ServiceSerializerClient,
        'default': serializers.GenericActionSerializer,
        'metadata': serializers.ServiceSerializerClient
    }

    @action(methods=['post'], detail=True)
    def start(self, request, pk=None):
        task = start_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def shutdown(self, request, pk=None):
        task = shutdown_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def reset(self, request, pk=None):
        task = reset_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def stop(self, request, pk=None):
        task = stop_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def reboot(self, request, pk=None):
        task = reboot_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def status(self, request, pk=None):
        stats = get_vm_status(pk)
        return Response(stats, status=202)

    @action(methods=['post'], detail=True)
    def provision(self, request, pk=None):
        task = provision_service.delay(service_id=pk, password=None)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['get'], detail=True)
    def ips(self, request, pk=None):
        ips = get_vm_ips(pk)
        return Response(ips, status=202)

    # @action(methods=['get'], detail=True)
    # def tasks(self, request, pk=None):
    #     tasks = get_vm_tasks(pk)
    #     return Response(tasks, status=202)


    @action(methods=['get'], detail=True)
    def console(self, request, pk=None):
        try:
            service_id = pk
        except KeyError:
            raise
        else:
            service = models.Service.objects.get(id=pk)
            if not service.machine_id:
                return Response({'error': 'No machine provisioned for this service'}, status=500)
            proxmox_user = f'inveterate{service.owner_id}'
            password = ''.join(
                random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation) for _ in
                range(10))
            proxmox = ProxmoxAPI(service.node.cluster.host, user=service.node.cluster.user, token_name='inveterate',
                                 token_value=service.node.cluster.key,
                                 verify_ssl=False, port=8006)

            try:
                proxmox.access.users.post(userid=f"{proxmox_user}@pve", password=password)
            except ResourceException as e:
                if "already exists" in str(e):
                    proxmox.access.users(f"{proxmox_user}@pve").delete()
                    proxmox.access.users.post(userid=f"{proxmox_user}@pve", password=password)
            proxmox.access.acl.put(path=f"/vms/{service.machine_id}", roles=["PVEVMConsole"],
                                   users=[f"{proxmox_user}@pve"])
            type = "lxc" if service.service_plan.type == "lxc" else "qemu"
            response = Response(
                {"username": f"{proxmox_user}@pve",
                 "password": password,
                 "node": service.node.name,
                 "machine": service.machine_id,
                 "type": type}
            )
        return response

    def get_queryset(self):
        if self.request.user.is_staff:
            return models.Service.objects.all().exclude(status='destroyed').order_by('pk')
        return models.Service.objects.filter(owner=self.request.user).exclude(status='destroyed').order_by('pk')


class DashboardViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = models.DashboardSummary.objects.order_by('pk')
    serializer_class = serializers.DashboardSummarySerializer

    @action(methods=['get'], detail=False)
    def summary(self, request):
        user_count = UserModel.objects.count()
        plan_count = models.Plan.objects.count()
        ip_count = models.IP.objects.count()
        template_count = models.Template.objects.count()
        service_count = models.Service.objects.count()
        node_count = models.Node.objects.count()
        data = {
            'users': user_count,
            'plans': plan_count,
            'ips': ip_count,
            'templates': template_count,
            'services': service_count,
            'nodes': node_count
        }
        return Response(data, status=202)
