import ipaddress
import re

#from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes, SerializerMethodField

from . import models
from .tasks import provision_service, assign_ips


from django.contrib.auth import get_user_model
from rest_framework.serializers import SerializerMethodField

UserModel = get_user_model()


class IPPoolSerializer(serializers.ModelSerializer):
    generate_ips = serializers.BooleanField(default=True, write_only=True, required=False)
    start_address = serializers.CharField(max_length=255, write_only=True, required=False)
    end_address = serializers.CharField(max_length=255, write_only=True, required=False)

    class Meta:
        model = models.IPPool
        fields = '__all__'

    def to_internal_value(self, data):
        data = data.copy()
        if isinstance(data['nodes'], str):
            data['nodes'] = data['nodes']
        return super().to_internal_value(data)

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
                        models.IP.objects.create(pool=ip_pool, value=str(ip))
                    except IntegrityError:
                        pass
        return ip_pool


class ClusterSerializer(serializers.ModelSerializer):
    __str__ = SerializerMethodField('display_name')
    key = serializers.CharField(write_only=True)

    def display_name(self, obj):
        return obj.name

    class Meta:
        model = models.Cluster
        fields = ('id','__str__','name','host','user','key')


class NodeSerializer(serializers.ModelSerializer):
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.name

    class Meta:
        model = models.Node
        fields = ('id','name','size','ram','swap','bandwidth','cores', 'cluster','__str__')


class NodeDiskSerializer(serializers.ModelSerializer):
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.name

    class Meta:
        model = models.NodeDisk
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
        model = models.Plan
        fields = '__all__'


class ServicePlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.ServicePlan
        fields = '__all__'


class ServicePlanSerializerClient(ServicePlanSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['template']:
                self.fields[field].read_only = True


class Owner(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = UserModel.objects.all()
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
    plan_name = serializers.ReadOnlyField(source='plan.name')
    # plan = serializers.SlugRelatedField(slug_field='name', queryset=Plan.objects.all())
    # node = serializers.SlugRelatedField(slug_field='name', queryset=Node.objects.all())
    template = serializers.SlugRelatedField(slug_field='name', queryset=models.Template.objects.all(), write_only=True)
    password = serializers.CharField(write_only=True, required=False)
    # machine_id = serializers.CharField(required=False)
    hostname = serializers.CharField(validators=[domain_validator])
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.hostname

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field in ['service_plan', 'machine_id', 'status_msg']:
                self.fields[field].read_only = True

    class Meta:
        model = models.Service
        fields = (
            'id', 'plan_name', 'owner', 'password', 'template', 'machine_id', 'hostname', 'plan',
            'node', 'status', 'service_plan', 'status_msg', '__str__'
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
        request = self.context.get('request', None)
        sps = ServicePlanSerializer()
        plan_fields = [f.name for f in models.PlanBase._meta.fields if f.name != "id"]
        plan_values = dict([(x, getattr(validated_data["plan"], x)) for x in plan_fields])
        service_plan = sps.create(plan_values)
        password = validated_data.pop("password", None)
        template = validated_data.pop("template", None)
        if "owner" not in validated_data:
            validated_data["owner"] = UserModel.objects.get(username=request.user)
        if "node" not in validated_data:
            inventory = models.Inventory.objects.filter(plan=validated_data["plan"]).first()
            validated_data["node"] = inventory.node
        if template:
            service_plan.template = template
            service_plan.type = template.type
        service = super().create(validated_data)
        service_plan.storage = service.node.node_disk.filter(primary=True).first()
        service_plan.save()
        service.service_plan = service_plan
        service.save()
        assign_ips(service.id)
        provision_service.delay(service.id, password)
        return service


class ServiceSerializerClient(ServiceSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['hostname', 'password', 'plan', 'template']:
                self.fields[field].read_only = True


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Inventory
        fields = '__all__'


class IPSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.IP
        fields = '__all__'

class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Template
        fields = '__all__'


class DashboardSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DashboardSummary
        fields = '__all__'


class GenericActionSerializer(serializers.Serializer):
    pass
