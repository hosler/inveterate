from django.conf.urls import url, include
import core.views as views
import core.viewsets as viewsets
from rest_framework import routers
from django.urls import path, re_path
from core.decorators.anonymouse_required import anonymous_required
#from account.decorators import login_required
from django.contrib.auth.decorators import login_required


router = routers.DefaultRouter()
router.register(r'plans', viewsets.PlanViewSet, basename='plan')
router.register(r'services', viewsets.ServiceViewSet, basename='service')
router.register(r'pools', viewsets.IPPoolViewSet, basename='pool')
router.register(r'ips', viewsets.IPViewSet, basename='ip')
#router.register(r'config', viewsets.ConfigSettingsViewSet, basename='config')
router.register(r'networks', viewsets.ServiceNetworkViewSet, basename='network')
router.register(r'templates', viewsets.TemplateViewSet, basename='template')
router.register(r'nodes', viewsets.VMNodeViewSet, basename='node')
router.register(r'node-disks', viewsets.NodeDiskViewSet, basename='node-disk')
router.register(r'inventory', viewsets.InventoryViewSet, basename='inventory')
router.register(r'billing', viewsets.BillingTypeViewSet, basename='billing')
router.register(r'blesta', viewsets.BlestaBackendViewSet, basename='blesta')
router.register(r'domain', viewsets.DomainViewSet, basename='domain')

# dashboard_urls = [
#     #re_path('^configs/$', login_required(views.ConfigSettingsView.as_view()), name='configs'),
#     re_path('^services/$', login_required(views.ServiceView.as_view()), name='services'),
#     re_path(r'^services/(?P<pk>\d+)/$', login_required(views.ServiceView.as_view()), name='services'),
#     re_path('^services/billing/$', login_required(views.Billing.as_view()), name='billing'),
#     re_path('^templates/$', login_required(views.TemplateView.as_view()), name='templates'),
#     re_path('^plans/$', login_required(views.PlanView.as_view()), name='plans'),
#     re_path('^ips/$', login_required(views.IPView.as_view()), name='ips'),
#     re_path('^pools/$', login_required(views.IPPoolView.as_view()), name='pools'),
#     re_path('^nodes/$', login_required(views.VMNodeView.as_view()), name='nodes'),
#     re_path('^node-disks/$', login_required(views.NodeDiskView.as_view()), name='node-disks'),
#     re_path('^billing/$', login_required(views.BillingTypeView.as_view()), name='billing'),
# ]

urlpatterns = [
    #path('', anonymous_required(views.Pricing.as_view()), name='pricing'),
    #path('', include((dashboard_urls, "dashboard"))),
    #path('order/', login_required(views.OrderForm.as_view()), name='order'),
    #e_path('^api/provision/$', login_required(views.ProvisionService.as_view())),
    #re_path('^api/console/$', login_required(views.Console.as_view()), name='console'),
    re_path('^api/', include(router.urls)),
]

