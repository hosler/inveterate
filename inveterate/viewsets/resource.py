from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .base import DynamicPageModelViewSet
from .. import models
from .. import serializers
from ..permissions import ReadOnlyAnonymous
from ..tasks import calculate_inventory


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
