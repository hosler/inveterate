from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .base import DynamicPageModelViewSet
from .. import models
from .. import serializers
from ..permissions import ReadOnly, ReadOnlyAnonymous
from ..tasks import calculate_inventory, import_kvm_template


class IPPoolViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    throttle_scope = 'admin'
    queryset = models.IPPool.objects.order_by('pk')
    serializer_class = serializers.IPPoolSerializer
    filterset_fields = ['type', 'internal']
    search_fields = ['name']
    ordering_fields = ['id', 'name', 'created']

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
    throttle_scope = 'public'
    queryset = models.Inventory.objects.order_by('pk')
    serializer_class = serializers.InventorySerializer

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return serializers.InventorySerializer
        return serializers.InventorySerializerClient

    @action(methods=['post'], detail=False)
    def calculate(self, request):
        task = calculate_inventory.delay()
        return Response({"task_id": task.id}, status=202)


class IPViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    throttle_scope = 'admin'
    queryset = models.IP.objects.order_by('pk')
    serializer_class = serializers.IPSerializer
    filterset_fields = ['pool', 'owner']
    search_fields = ['value']
    ordering_fields = ['id', 'value', 'created']

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
        return Response(stats)


class PlanViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | ReadOnlyAnonymous]
    throttle_scope = 'public'
    queryset = models.Plan.objects.order_by('pk')
    serializer_class = serializers.PlanSerializer
    search_fields = ['name']
    ordering_fields = ['id', 'name', 'size', 'ram', 'cores', 'created']

    @action(methods=['get'], detail=False, permission_classes=[IsAdminUser])
    def stats(self, request, pk=None):
        stats = {
            'plans': {
                'type': 'count',
                'label': 'Plans',
                'value': models.Plan.objects.all().count()
            }
        }
        return Response(stats)


class AppProfileViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | ReadOnlyAnonymous]
    throttle_scope = 'public'
    queryset = models.AppProfile.objects.order_by('pk')
    serializer_class = serializers.AppProfileSerializer
    search_fields = ['name']
    ordering_fields = ['id', 'name', 'created']

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return serializers.AppProfileSerializer
        return serializers.AppProfileSerializerClient


class TemplateViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser | ReadOnlyAnonymous]
    throttle_scope = 'public'
    queryset = models.Template.objects.order_by('pk')
    serializer_class = serializers.TemplateSerializer
    filterset_fields = ['type', 'status']
    search_fields = ['name']
    ordering_fields = ['id', 'name', 'type', 'created']

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return serializers.TemplateSerializer
        return serializers.TemplateSerializerClient

    @action(methods=['get'], detail=False, permission_classes=[IsAdminUser])
    def stats(self, request, pk=None):
        stats = {
            'templates': {
                'type': 'count',
                'label': 'KVM Plans',
                'value': models.Template.objects.all().count()
            }
        }
        return Response(stats)

    @action(methods=['post'], detail=True)
    def reimport(self, request, pk=None):
        template = self.get_object()
        if template.type != 'kvm':
            return Response(
                {'detail': 'Only KVM templates can be re-imported.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not template.source_url:
            return Response(
                {'detail': 'source_url is required for cloud image import.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        template.file = ''
        template.status = 'pending'
        template.status_msg = ''
        template.save()
        task = import_kvm_template.delay(template.id)
        return Response({'task_id': task.id}, status=202)
