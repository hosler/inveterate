from rest_framework import serializers
from .models import IPPool, Inventory, IP, Plan, Service, \
    ServicePlan, Template, ServiceNetwork, Config, NodeDisk,\
    BillingType, Cluster, Node, BlestaBackend, Domain, NodeDisk, PlanBase
from django.db import transaction
import ipaddress
from proxmoxer import ProxmoxAPI
from django.contrib.auth.models import User
from django.db import IntegrityError
from .tasks import provision_service, provision_billing
from nginx.config.api import Config, Section, Location

class SelectFieldModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        select_fields = kwargs.pop('select_fields', None)
        super().__init__(*args, **kwargs)

        if select_fields:
            # for multiple fields in a list
            for field_name in list(self.fields.keys()):
                if field_name not in select_fields:
                    self.fields.pop(field_name)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username']


class BlestaBackendSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlestaBackend
        fields = '__all__'


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
        # if ip_pool.internal is True:
        #     for node in ip_pool.nodes.all():
        #         proxmox = ProxmoxAPI(node.host, user=node.user, token_name='inveterate',
        #                              token_value=node.key,
        #                              verify_ssl=False, port=8006)
        #         node = proxmox.nodes(node.name)
        #         node_rules = node.firewall.rules.get()
        #         rules = {}
        #         for node_rule in node_rules:
        #             rules[(node_rule["source"], node_rule["dest"])] = node_rule["action"]
        #         rule_key = (f'{ip_pool.network}/{ip_pool.mask}', f'{ip_pool.network}/{ip_pool.mask}')
        #         if rule_key in rules:
        #             if rules[rule_key] == "DROP":
        #                 continue
                # TODO: add guest to guest blocking rule here
        return ip_pool


class ConfigSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        fields = '__all__'


class NodeDiskSerializer(serializers.ModelSerializer):
    class Meta:
        model = NodeDisk
        fields = '__all__'


class ServiceNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceNetwork
        fields = '__all__'


class IPSerializer(serializers.ModelSerializer):
    class Meta:
        model = IP
        fields = '__all__'


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = '__all__'


class ClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cluster
        fields = '__all__'


class ClusterListSerializer(ClusterSerializer):
    def __init__(self, *args, **kwargs):
        super(ClusterListSerializer, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].read_only = True


class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = ('id', 'name', 'type', 'cluster', 'cores', 'size', 'ram', 'swap', 'bandwidth')


class BillingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingType
        fields = '__all__'


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class PlanNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ('name',)


class ServicePlanSerializer(serializers.ModelSerializer):
    template = serializers.SlugRelatedField(slug_field='name', queryset=Template.objects.all())
    storage = serializers.SlugRelatedField(slug_field='name', queryset=NodeDisk.objects.all())

    class Meta:
        model = ServicePlan
        exclude = ('id',)


class Owner(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = User.objects.all()
        request = self.context.get('request', None)
        if not request.user.is_superuser:
            queryset = queryset.filter(username=request.user)
        return queryset


class PlanRelatedField(serializers.Field):
    def to_representation(self, obj):
        return obj.name

    def get_value(self, data):
        plan_id = data['plan']
        return (plan_id,)

    def to_internal_value(self, data):
        return Plan.objects.get(pk=data[0])


class Wat(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = User.objects.all()
        return queryset

    def to_internal_value(self, data):
        return super().to_internal_value(data)


class ServiceSerializer(serializers.ModelSerializer):
    service_plan = ServicePlanSerializer()
    owner = Owner(slug_field='username')
    plan = serializers.SlugRelatedField(slug_field='name', queryset=Plan.objects.all())
    node = serializers.SlugRelatedField(slug_field='name', queryset=Node.objects.all())
    password = serializers.CharField(write_only=True, required=False)



    class Meta:
        model = Service
        fields = (
            'id', 'owner', 'password', 'billing_id', 'machine_id', 'hostname', 'plan', 'node', 'status', 'service_plan', 'billing_type'
        )

    # Use this method for the custom field
    def _user(self, obj):
        request = self.context.get('request', None)
        if request:
            return request.user

    # def to_internal_value(self, data):
    #     new_data = data.copy()
    #
    #     for attribute in list(new_data.keys()):
    #         if new_data[attribute] == "":
    #             new_data.pop(attribute)
    #
    #     if "plan" in new_data:
    #         try:
    #             plan = Plan.objects.get(name=new_data["plan"])
    #         except Plan.DoesNotExist:
    #             pass
    #         else:
    #             ps = PlanSerializer(plan)
    #             plan_data = ps.data
    #             plan_data.pop("id")
    #             for attribute in plan_data:
    #                 # if "service_plan." + attribute not in new_data:
    #                 #     if isinstance(plan_data[attribute], list):
    #                 #         new_data.setlist("service_plan." + attribute, plan_data[attribute])
    #                 #     else:
    #                 new_data["service_plan." + attribute] = plan_data[attribute]
    #     if "template" in new_data:
    #         template = new_data.pop("template")[0]
    #         new_data["service_plan.template"] = template
    #
    #     return super().to_internal_value(new_data)

    def update(self, instance, validated_data):
        if 'service_plan' in validated_data:
            service_plan_serializer = self.fields['service_plan']
            service_plan_instance = instance.service_plan
            service_plan_data = validated_data.pop('service_plan')
            service_plan_serializer.update(service_plan_instance, service_plan_data)
        password = validated_data.pop("password", None)
        service = super().update(instance, validated_data)
        provision_service.delay(service.id, password)
        return service

    def create(self, validated_data):
        sps = ServicePlanSerializer()
        if "service_plan" in validated_data:
            service_plan_data = validated_data.pop("service_plan")
            service_plan = sps.create(service_plan_data)
        elif "plan" in validated_data:
            plan_fields = [f.name for f in PlanBase._meta.fields if f.name != "id"]
            plan_values = dict( [(x, getattr(validated_data["plan"], x)) for x in plan_fields] )
            service_plan = sps.create(plan_values)
        password = validated_data.pop("password", None)
        template = validated_data.pop("template", None)
        if template:
            service_plan.template = template
            service_plan.type = template.type
        service = super().create(validated_data)
        service_plan.storage = service.node.node_disk.filter(primary=True).first()
        service_plan.save()
        service.service_plan = service_plan
        service.save()
        for i in range(service_plan.internal_ips):

            for pool in service_plan.ip_pools.all():
                if pool.internal is False:
                    continue
                with transaction.atomic():
                    ip = IP.objects.select_for_update(skip_locked=True).filter(owner=None, pool=pool).first()
                    if ip:
                        service_network = ServiceNetwork.objects.create(service=service)
                        ip.owner = service_network
                        ip.save()
                        break
        for i in range(service_plan.ipv4_ips):
            for pool in service_plan.ip_pools.all():
                if pool.type != "ipv4":
                    continue
                with transaction.atomic():
                    ip = IP.objects.select_for_update(skip_locked=True).filter(owner=None, pool=pool).first()
                    if ip:
                        service_network = ServiceNetwork.objects.create(service=service)
                        ip.owner = service_network
                        ip.save()
                        break
        for i in range(service_plan.ipv6_ips):

            for pool in service_plan.ip_pools.all():
                if pool.type != "ipv6":
                    continue
                with transaction.atomic():
                    ip = IP.objects.select_for_update(skip_locked=True).filter(owner=None, pool=pool).first()
                    if ip:
                        service_network = ServiceNetwork.objects.create(service=service)
                        ip.owner = service_network
                        ip.save()
                        break

        if service.billing_type is None:
            provision_service.delay(service.id, password)
        else:
            provision_billing(service.id)
            if service.billing_type.type == "blesta":
                provision_service.delay(service.id, password)
        return service


class NewServiceSerializer(ServiceSerializer):
    template = serializers.SlugRelatedField(slug_field='name', queryset=Template.objects.all(), required=False)
    owner = Owner(slug_field='username')

    # def create(self, validated_data):
    #     super().create(validated_data)

    class Meta:
        model = Service
        fields = (
            'owner', 'hostname', 'plan', 'node', 'password', 'template', 'billing_type'
        )


class CustomerServiceSerializer(ServiceSerializer):
    owner = Owner(slug_field='username')
    template = serializers.SlugRelatedField(slug_field='name', queryset=Template.objects.all(), required=False)
    service_plan = ServicePlanSerializer()

    def __init__(self, *args, **kwargs):
        super(CustomerServiceSerializer, self).__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['owner', 'hostname', 'password', 'template', 'plan', 'node', 'billing_type']:
                self.fields[field].read_only = True

    class Meta:
        model = Service
        fields = (
            'id', 'owner', 'hostname', 'plan', 'node', 'password', 'template', 'billing_type', 'service_plan'
        )


class CustomerServiceListSerializer(ServiceSerializer):
    template = serializers.SlugRelatedField(slug_field='name', queryset=Template.objects.all(), required=False)
    service_plan = ServicePlanSerializer()

    def __init__(self, *args, **kwargs):
        super(CustomerServiceListSerializer, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].read_only = True

    class Meta:
        model = Service
        fields = (
            'id', 'owner', 'hostname', 'plan', 'node', 'password', 'template', 'billing_type', 'service_plan'
        )

class OrderNewServiceSerializer(ServiceSerializer):
    template = serializers.SlugRelatedField(slug_field='name', queryset=Template.objects.all(), required=False)
    owner = Owner(slug_field='username')

    class Meta:
        model = Service
        fields = (
            'owner', 'hostname', 'plan', 'node', 'password', 'template'
        )


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = '__all__'
