from drf_auto_endpoint.endpoints import Endpoint
from drf_auto_endpoint.factories import serializer_factory
from drf_auto_endpoint.router import register
from rest_framework.permissions import IsAdminUser

from core import models
from core import serializers
from core import viewsets
from core.permissions import ReadOnly
from core.viewsets import DynamicPageModelViewSet
from users.viewsets import UserViewSet


class DynamicPageEndpoint(Endpoint):
    base_viewset = DynamicPageModelViewSet


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
class TemplateEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.Template


@register
class ClusterEndpoint(DynamicPageEndpoint):
    viewset = viewsets.ClusterViewSet


@register
class DomainEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.Domain


@register
class NodeDiskEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.NodeDisk


@register
class BlestaBackendEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.BlestaBackend


@register
class NodeEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.Node
    serializer = serializer_factory(model=model, fields=('id', 'name', 'type', 'cluster', 'cores', 'size', 'ram',
                                                         'swap', 'bandwidth'))


@register
class BillingTypeEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.BillingType


@register
class ServiceNetworkEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.ServiceNetwork


@register
class ServicePlanEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser | ReadOnly]
    model = models.ServicePlan


@register
class IPEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.IP


@register
class IPPoolEndpoint(DynamicPageEndpoint):
    viewset = viewsets.IPPoolViewSet


@register
class PlanEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser | ReadOnly]
    model = models.Plan
    serializer = serializers.PlanSerializer


@register
class InventoryEndpoint(DynamicPageEndpoint):
    viewset = viewsets.InventoryViewSet


@register
class ServiceEndpoint(DynamicPageEndpoint):
    viewset = viewsets.ServiceViewSet


@register
class DashboardEndpoint(DynamicPageEndpoint):
    viewset = viewsets.DashboardViewSet


@register
class UserEndpoint(DynamicPageEndpoint):
    viewset = UserViewSet
