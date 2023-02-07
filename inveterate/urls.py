from django.conf.urls import include
from django.urls import path
from rest_framework import routers
from . import viewsets
router = routers.SimpleRouter()
router.register(r'users', viewsets.UserViewSet)
router.register(r'clusters', viewsets.ClusterViewSet)
router.register(r'nodes', viewsets.NodeViewSet)
router.register(r'ippools', viewsets.IPPoolViewSet)
router.register(r'inventory', viewsets.InventoryViewSet)
router.register(r'ips', viewsets.IPViewSet)
router.register(r'plans', viewsets.PlanViewSet)
router.register(r'templates', viewsets.TemplateViewSet)
router.register(r'serviceplans', viewsets.ServicePlanViewSet, basename="serviceplan")
router.register(r'dashboard', viewsets.DashboardViewSet)
router.register(r'services', viewsets.DashboardViewSet, basename="service")

urlpatterns = router.urls

