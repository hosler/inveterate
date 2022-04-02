from drf_auto_endpoint.router import router, register
from drf_auto_endpoint.endpoints import Endpoint
from drf_auto_endpoint.factories import serializer_factory
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from core.permissions import ReadOnly, ReadOnlyAnonymous
from core import viewsets
from core import models
from core import serializers
from core import tasks
from core.viewsets import DynamicPageModelViewSet
from users.viewsets import UserViewSet
from drf_auto_endpoint.decorators import custom_action

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
    # ordering_fields = ('id',)


@register
class NodeDiskEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.NodeDisk
    # ordering_fields = ('id',)


@register
class BlestaBackendEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.BlestaBackend
    # ordering_fields = ('id',)


@register
class NodeEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.Node
    # ordering_fields = ('id',)
    serializer = serializer_factory(model=model, fields=('id', 'name', 'type', 'cluster', 'cores', 'size', 'ram',
                                                         'swap', 'bandwidth'))


@register
class BillingTypeEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.BillingType
    # ordering_fields = ('id',)


@register
class ServiceNetworkEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.ServiceNetwork
    # ordering_fields = ('id',)


@register
class ServicePlanEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.ServicePlan
    # ordering_fields = ('id',)


@register
class IPEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser]
    model = models.IP
    # ordering_fields = ('id',)


@register
class IPPoolEndpoint(DynamicPageEndpoint):
    viewset = viewsets.IPPoolViewSet


@register
class PlanEndpoint(DynamicPageEndpoint):
    permission_classes = [IsAdminUser | ReadOnly]
    model = models.Plan
    # ordering_fields = ('id',)
    serializer = serializers.PlanSerializer


@register
class InventoryEndpoint(DynamicPageEndpoint):
    viewset = viewsets.InventoryViewSet


@register
class ServiceEndpoint(DynamicPageEndpoint):
    viewset = viewsets.ServiceViewSet

    # @custom_action(method='POST')
    # def start(self, request, pk=None):
    #     task = tasks.start_vm.delay(pk)
    #     # return Response({"task_id": task.id}, status=202)


@register
class DashboardEndpoint(DynamicPageEndpoint):
    viewset = viewsets.DashboardViewSet


@register
class UserEndpoint(DynamicPageEndpoint):
    viewset = UserViewSet
