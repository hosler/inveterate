from drf_auto_endpoint.endpoints import Endpoint
from drf_auto_endpoint.factories import serializer_factory
from drf_auto_endpoint.router import register
from rest_framework.permissions import IsAdminUser

from . import models
from . import serializers
from . import viewsets
from .permissions import ReadOnly
from .viewsets import DynamicPageModelViewSet
from rest_framework_datatables.pagination import DatatablesPageNumberPagination


class DynamicPageEndpoint(Endpoint):
    base_viewset = DynamicPageModelViewSet
    pagination_class = DatatablesPageNumberPagination



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
    viewset = viewsets.TemplateViewSet


@register
class ClusterEndpoint(DynamicPageEndpoint):
    viewset = viewsets.ClusterViewSet


@register
class DomainEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.Domain


@register
class StreamEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.Stream


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
    viewset = viewsets.NodeViewSet


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
    viewset = viewsets.ServicePlanViewSet
    # permission_classes = [IsAdminUser | ReadOnly]
    # model = models.ServicePlan


@register
class IPEndpoint(DynamicPageEndpoint):
    viewset = viewsets.IPViewSet


@register
class IPPoolEndpoint(DynamicPageEndpoint):
    viewset = viewsets.IPPoolViewSet


@register
class PlanEndpoint(DynamicPageEndpoint):
    viewset = viewsets.PlanViewSet


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
    viewset = viewsets.UserViewSet
