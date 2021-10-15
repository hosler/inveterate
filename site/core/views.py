from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
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
    NodeDiskSerializer

from .models import Service, BillingType, Inventory

from .forms import OrderProfileForm, OrderCustomizeVMForm, OrderPackageForm, NewServiceForm

from .tasks import provision_service, calculate_inventory, provision_billing

from app.blesta.api import BlestaApi
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException

import random
import string
import urllib
import stripe
import djstripe.settings
from django.conf import settings
from djstripe.models import Session, Customer, Product, Price
from django.http import QueryDict
from django.contrib.sites.models import Site

#load hooks
import core.stripe_hooks


def get_field_headers(serializer, headers=None, name=None):
    if headers is None:
        headers = {}
    fields = serializer.get_fields()
    for attribute in fields:
        if name is None:
            field_name = attribute
        else:
            field_name = ".".join([name, attribute])
        if isinstance(fields[attribute], serializers.ModelSerializer):
            get_field_headers(fields[attribute], headers, field_name)
        elif isinstance(fields[attribute], serializers.SlugRelatedField):
            slug = ".".join([field_name, fields[attribute].slug_field])
            headers[attribute] = (field_name, slug)
        else:
            headers[attribute] = (field_name, field_name)
    return headers


class SerializedAjaxFormView(UserPassesTestMixin, TemplateView):
    template_name = 'dashboard.html'
    serializer = None
    exclude_headers = None
    api = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        serializer = self.serializer()
        headers = get_field_headers(serializer)
        if self.exclude_headers is not None:
            for header in self.exclude_headers:
                if header in headers:
                    headers.pop(header)
        pk = context['view'].kwargs.get('pk', '')
        ctx = {'headers': headers, 'api': reverse(f'{self.api}-list'), 'pk': pk, "key": djstripe.settings.STRIPE_PUBLIC_KEY}
        context.update(ctx)
        return context

    def get(self, request, pk=None, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ConfigSettingsView(SerializedAjaxFormView):
    serializer = ConfigSettingsSerializer
    api = 'config'

    def test_func(self):
        return self.request.user.is_superuser


class VMNodeView(SerializedAjaxFormView):
    serializer = VMNodeSerializer
    api = 'node'

    def test_func(self):
        return self.request.user.is_superuser


class NodeDiskView(SerializedAjaxFormView):
    serializer = NodeDiskSerializer
    api = 'node-disk'

    def test_func(self):
        return self.request.user.is_superuser


class BillingTypeView(SerializedAjaxFormView):
    serializer = BillingTypeSerializer
    api = 'billing'

    def test_func(self):
        return self.request.user.is_superuser


class ServiceView(SerializedAjaxFormView):
    template_name = 'services.html'
    serializer = ServiceSerializer
    exclude_headers = ["ip_pools", "password"]
    api = 'service'
    form = NewServiceForm


    def test_func(self):
        return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form()
        return context


class IPPoolView(SerializedAjaxFormView):
    serializer = IPPoolSerializer
    api = 'pool'

    def test_func(self):
        return self.request.user.is_staff


class IPView(SerializedAjaxFormView):
    serializer = IPSerializer
    api = 'ip'

    def test_func(self):
        return self.request.user.is_staff


class PlanView(SerializedAjaxFormView):
    serializer = PlanSerializer
    api = 'plan'

    def test_func(self):
        return self.request.user.is_staff


class TemplateView(SerializedAjaxFormView):
    serializer = TemplateSerializer
    api = 'template'

    def test_func(self):
        return self.request.user.is_staff



class Billing(View):
    template_name = "billing.html"

    def post(self, request, *args, **kwargs):
        try:
            service_id = request.POST["service_id"]
        except KeyError:
            raise
        service = Service.objects.get(id=service_id)
        if service.billing_type is None:
            return render(request, self.template_name)
        if service.billing_type.type == "blesta":
            billing_backend = service.billing_type.backend
            blesta = BlestaApi(billing_backend.host, billing_backend.user,
                               billing_backend.key)
            invoices = blesta.get_service_invoices(service.billing_id)
            if len(invoices) > 0:
                user_id = blesta.search_user(request.user.email)["id"]
                client_id = blesta.get_client_from_user(user_id)["id"]
                contact_info = blesta.get_contacts(client_id)[0]
                contact_info["country"] = {'alpha2': contact_info["country"]}
                contact_info["state"] = {"code": contact_info["state"]}
                pay_links = blesta.create_pay_links(contact_info, invoices[0]["due"], "USD")
                return render(request, self.template_name, {"type": "blesta", "invoice": invoices[0], "pay_links": pay_links})
        elif service.billing_type.type == "stripe":
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
            return render(request, self.template_name,
                          {"type": "stripe",
                           "key": djstripe.settings.STRIPE_PUBLIC_KEY,
                           "service_id": service_id,
                           "sessionid": session.id})
        return render(request, self.template_name)


class Pricing(View):
    template_name = 'pricing.html'

    def get(self, request, *args, **kwargs):
        inventory = Inventory.objects.all()
        plans = []
        for item in inventory:
            plan = {
                "name": item.plan.name,
                "price": item.plan.price,
                "period": item.plan.period,
                "ram": item.plan.ram,
                "cores": item.plan.cores,
                "bandwidth": item.plan.bandwidth,
                "size": item.plan.size
            }
            if item.plan.ipv6_ips > 0:
                plan["ipv6"] = item.plan.ipv6_ips
            if item.plan.ipv4_ips > 0:
                plan["ipv4"] = item.plan.ipv4_ips
            if item.plan.internal_ips > 0:
                plan["internal_ips"] = item.plan.internal_ips

            plans.append(plan)
        return render(request, self.template_name, {"plans": plans})


class OrderForm(View):
    template_name = 'order.html'

    def get(self, request, *args, **kwargs):
        inventory = Inventory.objects.all()
        plans = []
        for item in inventory:
            plan = {
                "id": item.plan.id,
                "name": item.plan.name,
                "price": item.plan.price,
                "period": item.plan.period,
                "ram": item.plan.ram,
                "cores": item.plan.cores,
                "bandwidth": item.plan.bandwidth,
                "size": item.plan.size
            }
            if item.plan.ipv6_ips > 0:
                plan["ipv6"] = item.plan.ipv6_ips
            if item.plan.ipv4_ips > 0:
                plan["ipv4"] = item.plan.ipv4_ips
            if item.plan.internal_ips > 0:
                plan["internal_ips"] = item.plan.internal_ips

            plans.append(plan)
        profile_form = OrderProfileForm()
        customize_form = OrderCustomizeVMForm()
        package_form = OrderPackageForm()
        ctx = {
            'profile_form': profile_form,
            'customize_form': customize_form,
            'package_form': package_form,
            'plans': plans
        }
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        profile_form = OrderProfileForm(request.POST)
        customize_form = OrderCustomizeVMForm(request.POST)
        package_form = OrderPackageForm(request.POST)
        if profile_form.is_valid() and customize_form.is_valid() and package_form.is_valid():
            try:
                billing_type = BillingType.objects.get(name='Stripe').id
            except BillingType.DoesNotExist:
                billing_type = None

            node = Inventory.objects.all().filter(plan_id=package_form.cleaned_data['package'].id, quantity__gt=0).first().node
            data = {
                'owner': request.user.username,
                'plan': package_form.cleaned_data['package'],
                'template': customize_form.cleaned_data['template'],
                'hostname': customize_form.cleaned_data['hostname'],
                'password': customize_form.cleaned_data['password'],
                'node': node,
                'billing_type': billing_type
            }
            q = QueryDict(mutable=True)
            q.update(data)
            new_service_serializer = ServiceSerializer(data=q, context={'request': request})
            new_service_serializer.is_valid()
            service = new_service_serializer.save()
            return redirect(f"/services/{service.id}/#billing")
        else:
            ctx = {
                'profile_form': profile_form,
                'customize_form': customize_form,
                'package_form': package_form
            }
            return render(request, self.template_name, ctx)
