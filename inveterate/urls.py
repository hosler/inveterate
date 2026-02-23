from rest_framework import routers
from . import viewsets

app_name = "inveterate"

router = routers.DefaultRouter()
router.register(r'apps', viewsets.AppProfileViewSet)
router.register(r'clusters', viewsets.ClusterViewSet)
router.register(r'nodes', viewsets.NodeViewSet)
router.register(r'ippools', viewsets.IPPoolViewSet)
router.register(r'inventory', viewsets.InventoryViewSet)
router.register(r'ips', viewsets.IPViewSet)
router.register(r'plans', viewsets.PlanViewSet)
router.register(r'templates', viewsets.TemplateViewSet)
router.register(r'serviceplans', viewsets.ServicePlanViewSet, basename="serviceplan")
router.register(r'dashboard', viewsets.DashboardViewSet, basename="dashboard")
router.register(r'services', viewsets.ServiceViewSet, basename="service")
router.register(r'nodedisks', viewsets.NodeDiskViewSet)
router.register(r'customers', viewsets.CustomerViewSet)

urlpatterns = router.urls
