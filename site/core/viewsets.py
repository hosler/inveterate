from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAdminUser, SAFE_METHODS
from .tasks import provision_service, calculate_inventory

from rest_framework.decorators import action
from .serializers import \
    PlanSerializer, \
    ServiceSerializer, \
    IPPoolSerializer, \
    ServicePlanSerializer, \
    TemplateSerializer, \
    ServiceNetworkSerializer, \
    ConfigSettingsSerializer, \
    IPSerializer, \
    NewServiceSerializer, \
    OrderNewServiceSerializer, \
    VMNodeSerializer, \
    BillingTypeSerializer, \
    InventorySerializer, \
    BlestaBackendSerializer, \
    DomainSerializer, \
    NodeDiskSerializer

from .models import \
    IPPool, \
    IP, \
    Plan, \
    Service, \
    ServicePlan, \
    Template, \
    ServiceNetwork, \
    Config, \
    VMNode, \
    BillingType, \
    Inventory, \
    BlestaBackend, \
    Domain, \
    NodeDisk


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and
            request.method in SAFE_METHODS
        )


class FormModelViewSet(viewsets.ModelViewSet):

    def list(self, request, *args, **kwargs):
        if request.accepted_renderer.format == "form":
            if "pk" not in kwargs:
                serializer = self.get_serializer()
                return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def get_renderer_context(self):
        context = super().get_renderer_context()
        if "style" not in context:
            context['style'] = {}
        context['style']['template_pack'] = 'drf_horizontal'
        return context


class DomainViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Domain.objects.order_by('pk')
    serializer_class = DomainSerializer


class ConfigSettingsViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Config.objects.order_by('pk')
    serializer_class = ConfigSettingsSerializer


class NodeDiskViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = NodeDisk.objects.order_by('pk')
    serializer_class = NodeDiskSerializer


class BlestaBackendViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = BlestaBackend.objects.order_by('pk')
    serializer_class = BlestaBackendSerializer


class VMNodeViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = VMNode.objects.order_by('pk')
    serializer_class = VMNodeSerializer


class BillingTypeViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = BillingType.objects.order_by('pk')
    serializer_class = BillingTypeSerializer


class ServiceNetworkViewSet(FormModelViewSet):
    permission_classes = [ReadOnly]
    queryset = ServiceNetwork.objects.order_by('pk')
    serializer_class = ServiceNetworkSerializer


class TemplateViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Template.objects.order_by('pk')
    serializer_class = TemplateSerializer


class ServicePlanViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = ServicePlan.objects.order_by('pk')
    serializer_class = ServicePlanSerializer


class IPViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = IP.objects.order_by('pk')
    serializer_class = IPSerializer


class IPPoolViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = IPPool.objects.order_by('pk')
    serializer_class = IPPoolSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance:
            used_ips = IP.objects.filter(pool=instance, owner__isnull=False).count()
            if used_ips > 0:
                return Response(data={'message': "IPs in pool are currently in use"},
                                status=status.HTTP_400_BAD_REQUEST)
        return super(IPPoolViewSet, self).destroy(request, *args, **kwargs)


class PlanViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Plan.objects.order_by('pk')
    serializer_class = PlanSerializer


class InventoryViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Inventory.objects.order_by('pk')
    serializer_class = InventorySerializer

    @action(detail=False)
    def calculate(self, request):
        calculate_inventory.delay()
        return Response({'status': 'ok'})


class ServiceViewSet(FormModelViewSet):
    permission_classes = [IsAdminUser | ReadOnly]
    serializer_class = ServiceSerializer

    admin_serializer_classes = {
        'list': NewServiceSerializer,
    }
    client_serializer_classes = {
        'list': OrderNewServiceSerializer,
        'retrieve': ServiceSerializer
    }
    default_serializer_class = serializer_class

    @action(detail=True)
    def provision(self, request, pk=None):
        provision_service.delay(pk, password='default')
        return Response({'status': 'ok'})

    def get_queryset(self):
        if self.request.user.is_staff:
            return Service.objects.all().exclude(status='destroyed').order_by('pk')
        return Service.objects.filter(owner=self.request.user).exclude(status='destroyed').order_by('pk')

    def get_serializer_class(self):
        if self.request.accepted_renderer.format == "form":
            if self.request.user.is_staff:
                serializer_classes = self.admin_serializer_classes
            else:
                serializer_classes = self.client_serializer_classes
            return serializer_classes.get(self.action, self.default_serializer_class)
        else:
            return self.default_serializer_class