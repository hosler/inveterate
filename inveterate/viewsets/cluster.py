from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from requests.exceptions import ConnectionError, Timeout
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .. import models, serializers
from ..proxmox import get_proxmox_connection
from .base import DynamicPageModelViewSet, MultiSerializerViewSetMixin


class ClusterViewSet(MultiSerializerViewSetMixin, DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    throttle_scope = 'admin'
    queryset = models.Cluster.objects.order_by('pk')
    search_fields = ['name', 'host']
    ordering_fields = ['id', 'name', 'created']
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
    def status(self, request, pk=None):
        """Test Proxmox cluster connectivity with provided credentials"""

        try:
            # Test connection using proxmoxer

            cluster = models.Cluster.objects.get(pk=pk)
            proxmox = get_proxmox_connection(cluster)

            # Try to get cluster status and version to verify connection
            version = proxmox.version.get()
            cluster_info = proxmox.cluster.status.get()

            return Response({
                'success': True,
                'message': f'Connection successful! Proxmox version: {version.get("version", "Unknown")}'
            }, status=status.HTTP_200_OK)

        except (ConnectionError, Timeout):
            return Response({
                'success': False,
                'message': 'Connection failed: Unable to reach Proxmox server'
            }, status=status.HTTP_400_BAD_REQUEST)

        except ResourceException:
            # Usually authentication errors
            return Response({
                'success': False,
                'message': 'Authentication failed: Check username and API token'
            }, status=status.HTTP_401_UNAUTHORIZED)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=False)
    def test_connection(self, request):
        """Test Proxmox cluster connectivity with provided credentials"""
        # Get connection parameters from request
        host = request.data.get('host')
        user = request.data.get('user')
        key = request.data.get('key')

        if not all([host, user, key]):
            return Response({
                'success': False,
                'message': 'All connection fields are required (host, user, key)'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Test connection using proxmoxer
            verify_ssl = request.data.get('verify_ssl', False)
            proxmox = ProxmoxAPI(
                host,
                user=user,
                token_name='inveterate',
                token_value=key,
                verify_ssl=verify_ssl,
                port=8006,
                timeout=10,
            )

            # Try to get cluster status and version to verify connection
            version = proxmox.version.get()
            return Response({
                'success': True,
                'message': f'Connection successful! Proxmox version: {version.get("version", "Unknown")}'
            }, status=status.HTTP_200_OK)

        except (ConnectionError, Timeout):
            return Response({
                'success': False,
                'message': 'Connection failed: Unable to reach Proxmox server'
            }, status=status.HTTP_400_BAD_REQUEST)

        except ResourceException:
            # Usually authentication errors
            return Response({
                'success': False,
                'message': 'Authentication failed: Check username and API token'
            }, status=status.HTTP_401_UNAUTHORIZED)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=True)
    def nodes(self, request, pk=None):
        from ..tasks import get_cluster_resources
        stats = get_cluster_resources(pk=pk, query_type="node")
        return Response(stats)

    @action(methods=['get'], detail=True)
    def vms(self, request, pk=None):
        from ..tasks import get_cluster_resources
        stats = get_cluster_resources(pk=pk, query_type="vm")
        return Response(stats)

    @action(methods=['get'], detail=True)
    def disks(self, request, pk=None):
        from ..tasks import get_cluster_resources
        stats = get_cluster_resources(pk=pk, query_type="storage")
        return Response(stats)

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
        return Response(stats)
