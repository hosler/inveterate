from django.urls import path
from rest_framework import routers

from . import viewsets
from .viewsets.task import TaskStatusView

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
router.register(r'portgateways', viewsets.PortGatewayViewSet)
router.register(r'portblocks', viewsets.PortBlockViewSet, basename='portblock')
router.register(r'portforwards', viewsets.PortForwardViewSet, basename='portforward')
router.register(r'domainroutes', viewsets.DomainRouteViewSet, basename='domainroute')

urlpatterns = [
    path('tasks/<str:task_id>/', TaskStatusView.as_view(), name='api-task-status'),
] + router.urls
