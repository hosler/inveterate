from django.conf.urls import url, include
import core.viewsets as viewsets
from rest_framework import routers
from django.urls import path, re_path
from users.viewsets import UserViewSet

router = routers.DefaultRouter()
router.register(r'plans', viewsets.PlanViewSet, basename='plan')
router.register(r'services', viewsets.ServiceViewSet, basename='service')
router.register(r'pools', viewsets.IPPoolViewSet, basename='pool')
router.register(r'ips', viewsets.IPViewSet, basename='ip')
#router.register(r'config', viewsets.ConfigSettingsViewSet, basename='config')
router.register(r'networks', viewsets.ServiceNetworkViewSet, basename='network')
router.register(r'templates', viewsets.TemplateViewSet, basename='template')
router.register(r'clusters', viewsets.ClusterViewSet, basename='cluster')
router.register(r'nodes', viewsets.NodeViewSet, basename='node')
router.register(r'node-disks', viewsets.NodeDiskViewSet, basename='node-disk')
router.register(r'inventory', viewsets.InventoryViewSet, basename='inventory')
router.register(r'billing', viewsets.BillingTypeViewSet, basename='billing')
router.register(r'blesta', viewsets.BlestaBackendViewSet, basename='blesta')
router.register(r'domains', viewsets.DomainViewSet, basename='domain')
router.register(r'users', UserViewSet, basename='user')
router.register(r'dashboard', viewsets.DashboardViewSet, basename='dashboard')

def trigger_error(request):
    division_by_zero = 1 / 0


urlpatterns = [
    re_path('^api/', include(router.urls)),
    path('api/sentry-debug/', trigger_error),
]

