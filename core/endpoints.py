from drf_auto_endpoint.router import router, register
from drf_auto_endpoint.endpoints import Endpoint
from drf_auto_endpoint.factories import serializer_factory
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from core.permissions import ReadOnly, ReadOnlyAnonymous
from core import viewsets
from core import models
from core import serializers


class MultiSerializerViewSetMixin:
    def get_serializer(self, data=None):
        if self.context['request'].user:
            try:
                if data is None:
                    return self.admin_serializer_action_classes[self.action]
                else:
                    return self.admin_serializer_action_classes[self.action](data)
            except (KeyError, AttributeError):
                return super(MultiSerializerViewSetMixin, self).get_serializer_class()
        else:
            try:
                if data is None:
                    return self.serializer_action_classes[self.action]
                else:
                    return self.serializer_action_classes[self.action](data)
            except (KeyError, AttributeError):
                return super(MultiSerializerViewSetMixin, self).get_serializer_class()


@register
class DomainEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.Domain
    ordering_fields = ('id',)
    page_size = 10


@register
class NodeDiskEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.NodeDisk
    ordering_fields = ('id',)


@register
class BlestaBackendEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.BlestaBackend
    ordering_fields = ('id',)


@register
class NodeEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.Node
    ordering_fields = ('id',)
    serializer = serializer_factory(model=model, fields=('id', 'name', 'type', 'cluster', 'cores', 'size', 'ram',
                                                         'swap', 'bandwidth'))


@register
class BillingTypeEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.BillingType
    ordering_fields = ('id',)


@register
class ServiceNetworkEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.ServiceNetwork
    ordering_fields = ('id',)


@register
class ServicePlanEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.ServicePlan
    ordering_fields = ('id',)


@register
class IPEndpoint(Endpoint):
    permission_classes = [IsAdminUser]
    model = models.IP
    ordering_fields = ('id',)


@register
class IPPoolEndpoint(Endpoint):
    viewset = viewsets.IPPoolViewSet


@register
class PlanEndpoint(Endpoint):
    permission_classes = [IsAdminUser | ReadOnly]
    model = models.Plan
    ordering_fields = ('id',)
    serializer = serializers.PlanSerializer


@register
class InventoryEndpoint(Endpoint):
    viewset = viewsets.InventoryViewSet


@register
class ServiceEndpoint(Endpoint):
    viewset = viewsets.ServiceViewSet


@register
class DashboardEndpoint(Endpoint):
    viewset = viewsets.DashboardViewSet
