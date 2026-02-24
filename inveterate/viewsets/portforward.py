from rest_framework.permissions import IsAdminUser, IsAuthenticated

from .base import DynamicPageModelViewSet, MultiSerializerViewSetMixin
from .. import models
from .. import serializers
from ..permissions import ReadOnly
from ..tasks import delete_npm_stream, delete_npm_proxy_host


class PortGatewayViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    throttle_scope = 'admin'
    queryset = models.PortGateway.objects.order_by('pk')
    serializer_class = serializers.PortGatewaySerializer


class PortBlockViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | ReadOnly]
    throttle_scope = 'authenticated'

    default_serializer_class = serializers.PortBlockSerializer
    admin_serializer_action_classes = {
        'list': serializers.PortBlockSerializer,
        'retrieve': serializers.PortBlockSerializer,
    }
    serializer_action_classes = {
        'list': serializers.PortBlockSerializerClient,
        'retrieve': serializers.PortBlockSerializerClient,
    }

    def get_queryset(self):
        qs = models.PortBlock.objects.select_related(
            'gateway', 'service_network__ip', 'service_network__service'
        ).prefetch_related('forwards').order_by('pk')
        if self.request.user.is_staff:
            return qs
        return qs.filter(service_network__service__owner=self.request.user)


class PortForwardViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | IsAuthenticated]
    throttle_scope = 'authenticated'
    filterset_fields = ['port_block', 'protocol', 'enabled']
    ordering_fields = ['id', 'external_port', 'created']

    default_serializer_class = serializers.PortForwardSerializer
    admin_serializer_action_classes = {
        'list': serializers.PortForwardSerializer,
        'retrieve': serializers.PortForwardSerializer,
        'update': serializers.PortForwardSerializer,
        'create': serializers.PortForwardSerializer,
    }
    serializer_action_classes = {
        'list': serializers.PortForwardSerializerClient,
        'retrieve': serializers.PortForwardSerializerClient,
        'update': serializers.PortForwardSerializerClient,
        'create': serializers.PortForwardSerializerClient,
    }

    def get_queryset(self):
        qs = models.PortForward.objects.select_related(
            'port_block__gateway', 'port_block__service_network__service'
        ).order_by('pk')
        if self.request.user.is_staff:
            return qs
        return qs.filter(port_block__service_network__service__owner=self.request.user)

    def perform_destroy(self, instance):
        if instance.npm_stream_id:
            delete_npm_stream.delay(instance.port_block.gateway_id, instance.npm_stream_id)
        instance.delete()


class DomainRouteViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | IsAuthenticated]
    throttle_scope = 'authenticated'
    filterset_fields = ['service', 'ssl', 'enabled']
    search_fields = ['domain']
    ordering_fields = ['id', 'domain', 'created']

    default_serializer_class = serializers.DomainRouteSerializer
    admin_serializer_action_classes = {
        'list': serializers.DomainRouteSerializer,
        'retrieve': serializers.DomainRouteSerializer,
        'update': serializers.DomainRouteSerializer,
        'create': serializers.DomainRouteSerializer,
    }
    serializer_action_classes = {
        'list': serializers.DomainRouteSerializerClient,
        'retrieve': serializers.DomainRouteSerializerClient,
        'update': serializers.DomainRouteSerializerClient,
        'create': serializers.DomainRouteSerializerClient,
    }

    def get_queryset(self):
        qs = models.DomainRoute.objects.select_related('service').order_by('pk')
        if self.request.user.is_staff:
            return qs
        return qs.filter(service__owner=self.request.user)

    def perform_destroy(self, instance):
        if instance.npm_proxy_host_id:
            # Find gateway via service's internal network
            internal_sn = instance.service.service_network.filter(
                ip__pool__internal=True
            ).select_related('port_block__gateway').first()
            if internal_sn and hasattr(internal_sn, 'port_block'):
                delete_npm_proxy_host.delay(
                    internal_sn.port_block.gateway_id, instance.npm_proxy_host_id
                )
        instance.delete()
