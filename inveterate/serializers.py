import ipaddress
import re

from django.core.validators import RegexValidator
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes, SerializerMethodField

from . import models
from .tasks import provision_service, sync_port_forward, sync_domain_route, delete_npm_stream, delete_npm_proxy_host


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
        fields = ('id','__str__','name','host','user','key','bandwidth')


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
    hostname_pattern = re.compile(
        r'^[a-zA-Z0-9]'  # Must start with alphanumeric
        r'(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'  # Middle: alphanumeric or hyphens
        r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'  # Optional dot-separated labels
    )
    hostname_validator = RegexValidator(hostname_pattern)
    owner = Owner(slug_field='id')
    plan_name = serializers.ReadOnlyField(source='service_plan.name')
    plan = serializers.PrimaryKeyRelatedField(queryset=models.Plan.objects.all(), write_only=True, required=False)
    template = serializers.SlugRelatedField(slug_field='name', queryset=models.Template.objects.all(), write_only=True)
    password = serializers.CharField(write_only=True, required=False)
    apps = serializers.PrimaryKeyRelatedField(queryset=models.AppProfile.objects.all(), many=True, required=False, write_only=True)
    hostname = serializers.CharField(validators=[hostname_validator])
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.hostname

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field in ['service_plan', 'machine_id', 'status_msg',
                         'bw_usage', 'bw_banked', 'bw_stale', 'bw_renewal_dtm']:
                self.fields[field].read_only = True

    class Meta:
        model = models.Service
        fields = (
            'id', 'plan_name', 'owner', 'password', 'template', 'machine_id', 'hostname', 'plan',
            'node', 'status', 'service_plan', 'status_msg', 'apps',
            'bw_usage', 'bw_banked', 'bw_stale', 'bw_renewal_dtm', '__str__'
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
            validated_data["owner"] = request.user
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


# ===================================================================
# Port Forwarding / Domain Routing Serializers
# ===================================================================

class PortGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PortGateway
        fields = '__all__'

    def to_internal_value(self, data):
        data = data.copy()
        if 'pools' in data and isinstance(data['pools'], str):
            data['pools'] = [int(n) for n in data['pools'].split(',') if n]
        return super().to_internal_value(data)


class PortForwardNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PortForward
        fields = ('id', 'external_port', 'internal_port', 'protocol', 'label', 'enabled', 'npm_stream_id')
        read_only_fields = ('npm_stream_id',)


class PortBlockSerializer(serializers.ModelSerializer):
    forwards = PortForwardNestedSerializer(many=True, read_only=True)
    gateway_host = serializers.ReadOnlyField(source='gateway.host')
    gateway_name = serializers.ReadOnlyField(source='gateway.name')
    internal_ip = serializers.ReadOnlyField(source='service_network.ip.value')
    service_id = serializers.ReadOnlyField(source='service_network.service_id')

    class Meta:
        model = models.PortBlock
        fields = (
            'id', 'gateway', 'gateway_host', 'gateway_name',
            'service_network', 'internal_ip', 'service_id',
            'port_start', 'port_end', 'forwards', 'created', 'updated',
        )


class PortBlockSerializerClient(PortBlockSerializer):
    class Meta(PortBlockSerializer.Meta):
        read_only_fields = (
            'id', 'gateway', 'gateway_host', 'gateway_name',
            'service_network', 'internal_ip', 'service_id',
            'port_start', 'port_end', 'forwards', 'created', 'updated',
        )


class PortForwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PortForward
        fields = '__all__'
        read_only_fields = ('npm_stream_id',)

    def validate_internal_port(self, value):
        if not 1 <= value <= 65535:
            raise serializers.ValidationError("internal_port must be between 1 and 65535.")
        return value

    def validate(self, attrs):
        port_block = attrs.get('port_block') or (self.instance.port_block if self.instance else None)
        external_port = attrs.get('external_port', getattr(self.instance, 'external_port', None))
        if port_block and external_port is not None:
            if not (port_block.port_start <= external_port <= port_block.port_end):
                raise serializers.ValidationError({
                    'external_port': f"Must be within port block range {port_block.port_start}-{port_block.port_end}."
                })
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        sync_port_forward.delay(instance.id)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        sync_port_forward.delay(instance.id)
        return instance


class PortForwardSerializerClient(PortForwardSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and not request.user.is_staff:
            self.fields['port_block'].queryset = models.PortBlock.objects.filter(
                service_network__service__owner=request.user
            )


class DomainRouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DomainRoute
        fields = '__all__'
        read_only_fields = ('npm_proxy_host_id',)

    def validate_forward_port(self, value):
        if not 1 <= value <= 65535:
            raise serializers.ValidationError("forward_port must be between 1 and 65535.")
        return value

    def validate(self, attrs):
        service = attrs.get('service') or (self.instance.service if self.instance else None)
        if service:
            # Service must have at least one internal IP with a gateway
            has_internal_gw = models.ServiceNetwork.objects.filter(
                service=service, ip__pool__internal=True
            ).filter(
                ip__pool__in=models.PortGateway.objects.values_list('pools', flat=True)
            ).exists()
            if not has_internal_gw:
                raise serializers.ValidationError({
                    'service': "Service must have an internal IP with a configured port gateway."
                })
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        sync_domain_route.delay(instance.id)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        sync_domain_route.delay(instance.id)
        return instance


class DomainRouteSerializerClient(DomainRouteSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and not request.user.is_staff:
            self.fields['service'].queryset = models.Service.objects.filter(
                owner=request.user
            ).exclude(status='destroyed')
