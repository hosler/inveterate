import ipaddress
import re

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import IntegrityError
from nginx.config.api import Section, Location
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes, SerializerMethodField

from .models import IPPool, Inventory, IP, Plan, Service, \
    ServicePlan, Template, NodeDisk, \
    Cluster, Node, Domain, PlanBase, DashboardSummary
from .tasks import provision_service, provision_billing, assign_ips


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = '__all__'

    def create(self, validated_data):
        domain = super().create(validated_data)
        name = validated_data.pop("name")
        section = Section(
            'server',
            Location(
                '/foo',
                proxy_pass='upstream',
            ),
            server_name=name,
            listen='80'
        )
        with open(f"/home/hosler/nfs/PycharmProjects/inveterate/conf/sites/{name}", "w") as f:
            f.write(str(section))

        return domain


class IPPoolSerializer(serializers.ModelSerializer):
    generate_ips = serializers.BooleanField(default=True, write_only=True, required=False)
    start_address = serializers.CharField(max_length=255, write_only=True, required=False)
    end_address = serializers.CharField(max_length=255, write_only=True, required=False)

    class Meta:
        model = IPPool
        fields = '__all__'

    def create(self, validated_data):
        generate_ips = validated_data.pop("generate_ips")
        start_address = validated_data.pop("start_address")
        end_address = validated_data.pop("end_address")
        networks = ipaddress.summarize_address_range(
            ipaddress.ip_address(start_address),
            ipaddress.ip_address(end_address))
        ip_pool = super().create(validated_data)
        if generate_ips is True:
            for network in networks:
                for ip in network:
                    try:
                        IP.objects.create(pool=ip_pool, value=str(ip))
                    except IntegrityError:
                        pass
        return ip_pool


class ClusterSerializer(serializers.ModelSerializer):
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.name

    class Meta:
        model = Cluster
        fields = '__all__'


class PlanSerializer(serializers.ModelSerializer):
    size = serializers.IntegerField(min_value=4)
    ram = serializers.IntegerField(min_value=64)
    swap = serializers.IntegerField(min_value=0)
    cores = serializers.IntegerField(min_value=1)
    bandwidth = serializers.IntegerField(min_value=0)
    cpu_units = serializers.IntegerField(min_value=1)
    cpu_limit = serializers.DecimalField(min_value=0, max_digits=3, decimal_places=2)
    ipv6_ips = serializers.IntegerField(min_value=0)
    ipv4_ips = serializers.IntegerField(min_value=0)
    internal_ips = serializers.IntegerField(min_value=0)

    class Meta:
        model = Plan
        fields = '__all__'


class ServicePlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = ServicePlan
        fields = '__all__'


class ServicePlanSerializerClient(ServicePlanSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['template']:
                self.fields[field].read_only = True


class Owner(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = User.objects.all()
        request = self.context.get('request', None)
        if not request.user.is_superuser:
            queryset = queryset.filter(username=request.user)
        return queryset


class ServiceSerializer(serializers.ModelSerializer):
    domain_pattern = re.compile(
        r'^(?:[a-zA-Z0-9]'  # First character of the domain
        r'(?:[a-zA-Z0-9-_]{0,61}[A-Za-z0-9])?\.)'  # Sub domain + hostname
        r'+[A-Za-z0-9][A-Za-z0-9-_]{0,61}'  # First 61 characters of the gTLD
        r'[A-Za-z]$'  # Last character of the gTLD
    )
    domain_validator = RegexValidator(domain_pattern)
    # service_plan = ServicePlanSerializer(read_only=True)
    owner = Owner(slug_field='id')
    # plan = serializers.SlugRelatedField(slug_field='name', queryset=Plan.objects.all())
    # node = serializers.SlugRelatedField(slug_field='name', queryset=Node.objects.all())
    password = serializers.CharField(write_only=True, required=False)
    # machine_id = serializers.CharField(required=False)
    hostname = serializers.CharField(validators=[domain_validator])
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.hostname

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field in ['service_plan', 'billing_id', 'machine_id', 'status_msg']:
                self.fields[field].read_only = True

    class Meta:
        model = Service
        fields = (
            'id', 'owner', 'password', 'billing_id', 'machine_id', 'hostname', 'plan', 'node', 'status', 'service_plan',
            'billing_type', 'status_msg', '__str__'
        )

    # Use this method for the custom field
    def _user(self, obj):
        request = self.context.get('request', None)
        if request:
            return request.user

    def update(self, instance, validated_data):
        # if 'service_plan' in validated_data:
        #     service_plan_serializer = self.fields['service_plan']
        #     service_plan_serializer.partial = True
        #     service_plan_instance = instance.service_plan
        #     service_plan_data = validated_data.pop('service_plan')
        #     service_plan_serializer.update(service_plan_instance, service_plan_data)
        password = validated_data.pop("password", None)
        raise_errors_on_nested_writes('update', self, validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        provision_service.delay(instance.id, password)
        return instance

    def create(self, validated_data):
        sps = ServicePlanSerializer()
        # if "service_plan" in validated_data:
        #     service_plan_data = validated_data.pop("service_plan")
        #     service_plan = sps.create(service_plan_data)
        # if "plan" in validated_data:
        plan_fields = [f.name for f in PlanBase._meta.fields if f.name != "id"]
        plan_values = dict([(x, getattr(validated_data["plan"], x)) for x in plan_fields])
        service_plan = sps.create(plan_values)
        password = validated_data.pop("password", None)
        # template = validated_data.pop("template", None)
        # if template:
        #     service_plan.template = template
        #     service_plan.type = template.type
        service = super().create(validated_data)
        service_plan.storage = service.node.node_disk.filter(primary=True).first()
        service_plan.save()
        service.service_plan = service_plan
        service.save()
        assign_ips(service.id)
        if service.billing_type is None:
            provision_service.delay(service.id, password)
        else:
            provision_billing(service.id)
            if service.billing_type.type == "blesta":
                provision_service.delay(service.id, password)
        return service


class ServiceSerializerClient(ServiceSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['hostname', 'password', 'plan']:
                self.fields[field].read_only = True


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = '__all__'


class DashboardSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardSummary
        fields = '__all__'


class GenericActionSerializer(serializers.Serializer):
    pass
