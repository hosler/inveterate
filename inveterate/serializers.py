import ipaddress
import re

from django.core.validators import RegexValidator
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes, SerializerMethodField

from . import models
from .tasks import provision_service


from django.contrib.auth import get_user_model

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
        if 'nodes' in data and isinstance(data['nodes'], str):
            data['nodes'] = [int(n) for n in data['nodes'].split(',') if n]
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
    owner = Owner(slug_field='id')
    plan_name = serializers.ReadOnlyField(source='service_plan.name')
    plan = serializers.PrimaryKeyRelatedField(queryset=models.Plan.objects.all(), write_only=True, required=False)
    template = serializers.SlugRelatedField(slug_field='name', queryset=models.Template.objects.all(), write_only=True)
    password = serializers.CharField(write_only=True, required=False)
    apps = serializers.PrimaryKeyRelatedField(queryset=models.AppProfile.objects.all(), many=True, required=False, write_only=True)
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
            'node', 'status', 'service_plan', 'status_msg', 'apps', '__str__'
        )

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        raise_errors_on_nested_writes('update', self, validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        provision_service.delay(instance.id, password)
        return instance

    def create(self, validated_data):
        request = self.context.get('request', None)
        plan = validated_data.pop("plan")
        password = validated_data.pop("password", None)
        template = validated_data.pop("template", None)
        apps = validated_data.pop("apps", [])

        # Snapshot plan fields into ServicePlan
        plan_fields = [f.name for f in models.PlanBase._meta.fields if f.name != "id"]
        plan_values = dict([(x, getattr(plan, x)) for x in plan_fields])
        plan_values['name'] = plan.name
        sps = ServicePlanSerializer()
        service_plan = sps.create(plan_values)

        if "owner" not in validated_data:
            validated_data["owner"] = UserModel.objects.get(username=request.user)
        if "node" not in validated_data:
            inventory = models.Inventory.objects.filter(plan=plan).first()
            validated_data["node"] = inventory.node
        if template:
            service_plan.template = template
            service_plan.type = template.type
        service = super().create(validated_data)
        service_plan.storage = service.node.node_disk.filter(primary=True).first()
        service_plan.save()
        if apps:
            service_plan.apps.set(apps)
        service.service_plan = service_plan
        service.save()
        # IP assignment happens inside provision_service task
        provision_service.delay(service.id, password)
        return service


class ServiceSerializerClient(ServiceSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['hostname', 'password', 'plan', 'template', 'apps']:
                self.fields[field].read_only = True


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Inventory
        fields = '__all__'


class IPSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.IP
        fields = '__all__'

class AppProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AppProfile
        fields = '__all__'


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Template
        fields = '__all__'
        read_only_fields = ('status', 'status_msg')

    def create(self, validated_data):
        template = super().create(validated_data)
        if template.type == 'kvm' and template.source_url:
            template.status = 'pending'
            template.save(update_fields=['status'])
            from .tasks import import_kvm_template
            import_kvm_template.delay(template.id)
        return template
