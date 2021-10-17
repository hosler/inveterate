from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import BasePermission, IsAdminUser, SAFE_METHODS
from .tasks import provision_service, calculate_inventory, start_vm, stop_vm, reboot_vm, reset_vm, shutdown_vm, provision_billing, get_vm_status
from django.contrib.sites.models import Site
import stripe
import djstripe.settings
from django.conf import settings
from djstripe.models import Session, Customer, Product, Price
from rest_framework.decorators import action
from .serializers import \
    PlanSerializer, \
    ServiceSerializer, \
    IPPoolSerializer, \
    ServicePlanSerializer, \
    TemplateSerializer, \
    ServiceNetworkSerializer, \
    ConfigSettingsSerializer, \
    IPSerializer, \
    NewServiceSerializer, \
    OrderNewServiceSerializer, \
    VMNodeSerializer, \
    BillingTypeSerializer, \
    InventorySerializer, \
    BlestaBackendSerializer, \
    DomainSerializer, \
    NodeDiskSerializer, \
    CustomerServiceSerializer, \
    CustomerServiceListSerializer

from .models import \
    IPPool, \
    IP, \
    Plan, \
    Service, \
    ServicePlan, \
    Template, \
    ServiceNetwork, \
    Config, \
    VMNode, \
    BillingType, \
    Inventory, \
    BlestaBackend, \
    Domain, \
    NodeDisk

import random
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
import string

class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and
            request.method in SAFE_METHODS
        )

class IsAuthenticated(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """

    def has_permission(self, request, view):
        if view.action in ['provision_billing', 'destroy']:
            return False

        return bool(
            request.user and
            request.user.is_authenticated
        )

class FormModelViewSet(viewsets.ModelViewSet):

    def list(self, request, *args, **kwargs):
        if request.accepted_renderer.format == "form":
            if "pk" not in kwargs:
                serializer = self.get_serializer()
                return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def get_renderer_context(self):
        context = super().get_renderer_context()
        if "style" not in context:
            context['style'] = {}
        context['style']['template_pack'] = 'drf_horizontal'
        return context


class DomainViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Domain.objects.order_by('pk')
    serializer_class = DomainSerializer


class ConfigSettingsViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Config.objects.order_by('pk')
    serializer_class = ConfigSettingsSerializer


class NodeDiskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = NodeDisk.objects.order_by('pk')
    serializer_class = NodeDiskSerializer


class BlestaBackendViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = BlestaBackend.objects.order_by('pk')
    serializer_class = BlestaBackendSerializer


class VMNodeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = VMNode.objects.order_by('pk')
    serializer_class = VMNodeSerializer


class BillingTypeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = BillingType.objects.order_by('pk')
    serializer_class = BillingTypeSerializer


class ServiceNetworkViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnly]
    queryset = ServiceNetwork.objects.order_by('pk')
    serializer_class = ServiceNetworkSerializer


class TemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Template.objects.order_by('pk')
    serializer_class = TemplateSerializer


class ServicePlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = ServicePlan.objects.order_by('pk')
    serializer_class = ServicePlanSerializer


class IPViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = IP.objects.order_by('pk')
    serializer_class = IPSerializer


class IPPoolViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = IPPool.objects.order_by('pk')
    serializer_class = IPPoolSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance:
            used_ips = IP.objects.filter(pool=instance, owner__isnull=False).count()
            if used_ips > 0:
                return Response(data={'message': "IPs in pool are currently in use"},
                                status=status.HTTP_400_BAD_REQUEST)
        return super(IPPoolViewSet, self).destroy(request, *args, **kwargs)


class PlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Plan.objects.order_by('pk')
    serializer_class = PlanSerializer


class InventoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Inventory.objects.order_by('pk')
    serializer_class = InventorySerializer

    @action(detail=False)
    def calculate(self, request):
        task = calculate_inventory.delay()
        return Response({"task_id": task.id}, status=202)


class MultiSerializerViewSetMixin(object):
    def get_serializer_class(self):
        if self.request.user.is_staff:
            try:
                return self.admin_serializer_action_classes[self.action]
            except (KeyError, AttributeError):
                return super(MultiSerializerViewSetMixin, self).get_serializer_class()
        else:
            try:
                return self.serializer_action_classes[self.action]
            except (KeyError, AttributeError):
                return super(MultiSerializerViewSetMixin, self).get_serializer_class()


class ServiceViewSet(MultiSerializerViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAdminUser | IsAuthenticated]

    serializer_class = CustomerServiceListSerializer
    admin_serializer_action_classes = {
        'list': ServiceSerializer,
        'retrieve': ServiceSerializer,
        'update': ServiceSerializer,
        'create': ServiceSerializer,
    }
    serializer_action_classes = {
        'list': CustomerServiceListSerializer,
        'retrieve': CustomerServiceSerializer,
        'update': CustomerServiceSerializer,
        'create': CustomerServiceListSerializer,
        'provision': CustomerServiceSerializer
    }

    @action(methods=['post'], detail=True)
    def start(self, request, pk=None):
        task = start_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def shutdown(self, request, pk=None):
        task = shutdown_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def reset(self, request, pk=None):
        task = reset_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def stop(self, request, pk=None):
        task = stop_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def reboot(self, request, pk=None):
        task = reboot_vm.delay(pk)
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def status(self, request, pk=None):
        stats = get_vm_status(pk)
        return Response(stats, status=202)

    @action(methods=['post', 'get'], detail=True)
    def provision(self, request, pk=None):
        if self.request.method == 'GET':
            return Response(data={'detail': 'Method "GET" not allowed.'},
                            status=status.HTTP_405_METHOD_NOT_ALLOWED)
        task = provision_service.delay(pk, password='default')
        return Response({"task_id": task.id}, status=202)

    @action(methods=['post'], detail=True)
    def provision_billing(self, request, pk=None):
        task = provision_billing.delay(pk)
        return Response({"task_id": task.id}, status=202)


    @action(detail=True)
    def billing(self, request, pk=None):
        try:
            service_id = pk
        except KeyError:
            raise
        service = Service.objects.get(id=service_id)
        customer = Customer.objects.get(subscriber_id=service.owner.id)
        try:
            session = Session.objects.get(customer=customer, client_reference_id=service_id)
        except Session.DoesNotExist:
            product = Product.objects.get(livemode=djstripe.settings.STRIPE_LIVE_MODE,
                                          name=service.plan.name,
                                          active=True)
            price = Price.objects.get(livemode=djstripe.settings.STRIPE_LIVE_MODE,
                                      active=True,
                                      product=product,
                                      unit_amount=int(service.plan.price * 100),
                                      recurring__interval=service.plan.period,
                                      recurring__interval_count=service.plan.term
                                      )
            site = Site.objects.get(pk=settings.SITE_ID)
            data = {
                'payment_method_types': ['card'],
                'client_reference_id': service_id,
                'customer': customer.id,
                'line_items': [{
                    'price': price.id,
                    'quantity': 1,
                }],
                'mode': 'subscription',
                'success_url': f'https://{site.domain}/services/{service_id}/',
                'cancel_url': f'https://{site.domain}/services/{service_id}/',
                'metadata': {
                    'inveterate_id': service_id
                },
                "subscription_data": {
                    'metadata': {
                        'inveterate_id': service_id
                    }
                }
            }
            stripe.api_key = djstripe.settings.STRIPE_SECRET_KEY
            session = stripe.checkout.Session.create(**data)
            Session._create_from_stripe_object(data=session)
        return Response(
                      {"type": "stripe",
                       "key": djstripe.settings.STRIPE_PUBLIC_KEY,
                       "service_id": service_id,
                       "sessionid": session.id})

    @action(methods=['post'], detail=True)
    def console_login(self, request, pk=None):
        try:
            service_id = pk
        except KeyError:
            raise
        else:
            service = Service.objects.get(id=pk)
            proxmox_user = f'inveterate{service.owner_id}'
            password = ''.join(
                random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation) for _ in
                range(10))
            proxmox = ProxmoxAPI(service.node.host, user=service.node.user, token_name='inveterate',
                                 token_value=service.node.key,
                                 verify_ssl=False, port=8006)

            try:
                proxmox.access.users.post(userid=f"{proxmox_user}@pve", password=password)
            except ResourceException as e:
                if "already exists" in str(e):
                    proxmox.access.users(f"{proxmox_user}@pve").delete()
                    proxmox.access.users.post(userid=f"{proxmox_user}@pve", password=password)
            proxmox.access.acl.put(path=f"/vms/{service.machine_id}", roles=["PVEVMConsole"],
                                   users=[f"{proxmox_user}@pve"])
            response = Response(
                {"username": f"{proxmox_user}@pve",
                 "password": password,
                 "url": f"wss://www.dhos.me/api2/json/nodes/{service.node.name}/qemu/{service.machine_id}/vncwebsocket"}
            )
        return response

    def create(self, request):
        if self.request.user.is_staff:
            return super(ServiceViewSet, self).create(request)
        raise MethodNotAllowed(request.method)

    def get_queryset(self):
        if self.request.user.is_staff:
            return Service.objects.all().exclude(status='destroyed').order_by('pk')
        return Service.objects.filter(owner=self.request.user).exclude(status='destroyed').order_by('pk')

