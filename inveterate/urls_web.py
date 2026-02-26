"""
Web interface URL patterns for Inveterate.

Host projects can include these with:
    path('', include('inveterate.urls_web')),
"""
from django.urls import path

from . import views

app_name = "inveterate-web"

urlpatterns = [
    # Authentication
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # Web Interface
    path('', views.home_view, name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('services/', views.ServiceListView.as_view(), name='services'),
    path('services/order/', views.ServiceOrderView.as_view(), name='service-order'),
    path('services/<int:service_id>/', views.ServiceDetailView.as_view(), name='service-detail'),
    path('services/<int:service_id>/console/', views.ServiceConsoleView.as_view(), name='service-console'),
    path('services/<int:service_id>/console/auth/', views.console_auth_view, name='console-auth'),
    path('services/<int:service_id>/console/termproxy/', views.console_termproxy_view, name='console-termproxy'),
    path('clusters/', views.ClusterListView.as_view(), name='clusters'),
    path('nodes/', views.NodeListView.as_view(), name='nodes'),
    path('dashboard/services/', views.AdminServiceListView.as_view(), name='admin-services'),
    path('dashboard/plans/', views.PlanListView.as_view(), name='admin-plans'),
    path('dashboard/templates/', views.TemplateListView.as_view(), name='admin-templates'),
    path('dashboard/apps/', views.AppProfileListView.as_view(), name='admin-apps'),
    path('dashboard/ips/', views.IPPoolListView.as_view(), name='admin-ips'),
]
