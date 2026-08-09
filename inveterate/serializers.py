import ipaddress
import re

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes, SerializerMethodField

from . import models
from .domain_verification import account_token, verification_record_name
from .tasks import (
    provision_service, sync_port_forward, sync_domain_route,
    delete_npm_stream, delete_npm_proxy_host, verify_domain_route,
)


from django.contrib.auth import get_user_model

UserModel = get_user_model()


class ServiceOperationConflict(serializers.ValidationError):
    status_code = 409
    default_detail = "An operation is already in progress for this service."


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
    host = serializers.SerializerMethodField()

    def display_name(self, obj):
        return obj.name

    def get_host(self, obj):
        return obj.cluster.host if obj.cluster else None

    class Meta:
        model = models.Node
        fields = ('id', 'name', 'host', 'size', 'ram', 'swap', 'bandwidth', 'cores', 'cluster', 'status', '__str__')


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
            queryset = queryset.filter(pk=request.user.pk)
        return queryset


_SSH_KEY_PREFIXES = (
    'ssh-rsa ', 'ssh-ed25519 ', 'ssh-dss ', 'ecdsa-sha2-',
    'sk-ssh-ed25519@openssh.com ', 'sk-ecdsa-sha2-',
)


class ServiceSerializer(serializers.ModelSerializer):
    hostname_pattern = re.compile(
        r'^[a-zA-Z0-9]'  # Must start with alphanumeric
        r'(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'  # Middle: alphanumeric or hyphens
        r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'  # Optional dot-separated labels
    )
    hostname_validator = RegexValidator(hostname_pattern)
    owner = Owner(slug_field='id')
    service_plan = ServicePlanSerializer(read_only=True)
    plan_name = serializers.ReadOnlyField(source='service_plan.name')
    plan = serializers.PrimaryKeyRelatedField(queryset=models.Plan.objects.all(), write_only=True, required=False)
    template = serializers.SlugRelatedField(slug_field='name', queryset=models.Template.objects.all(), write_only=True)
    password = serializers.CharField(write_only=True, required=False)
    apps = serializers.PrimaryKeyRelatedField(queryset=models.AppProfile.objects.all(), many=True, required=False, write_only=True)
    ssh_keys = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    hostname = serializers.CharField(validators=[hostname_validator])
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.hostname

    def validate_username(self, value):
        if value and not re.match(r'^[a-z_][a-z0-9_-]*$', value):
            raise serializers.ValidationError(
                "Username must start with a lowercase letter or underscore, "
                "and contain only lowercase letters, digits, underscores, and hyphens."
            )
        return value

    def validate_ssh_keys(self, value):
        if len(value) > 20:
            raise serializers.ValidationError("A maximum of 20 SSH keys may be provided.")
        for key in value:
            if not any(key.startswith(prefix) for prefix in _SSH_KEY_PREFIXES):
                raise serializers.ValidationError(
                    "Invalid SSH key format. Keys must start with a known type (e.g. ssh-rsa, ssh-ed25519)."
                )
            parts = key.split()
            if len(parts) < 2:
                raise serializers.ValidationError(
                    "Invalid SSH key format. Keys must have at least a type and base64 data."
                )
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field in ['service_plan', 'machine_id', 'status_msg',
                         'bw_usage', 'bw_banked', 'bw_stale', 'bw_renewal_dtm']:
                self.fields[field].read_only = True

    class Meta:
        model = models.Service
        fields = (
            'id', 'plan_name', 'owner', 'password', 'template', 'machine_id', 'hostname', 'username', 'plan',
            'node', 'status', 'service_plan', 'status_msg', 'apps', 'ssh_keys',
            'bw_usage', 'bw_banked', 'bw_stale', 'bw_renewal_dtm', 'created', '__str__'
        )

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        ssh_keys = validated_data.pop("ssh_keys", None)
        apps = validated_data.pop("apps", None)
        plan = validated_data.pop("plan", None)
        template = validated_data.pop("template", None)
        raise_errors_on_nested_writes('update', self, validated_data)

        relevant = password is not None or ssh_keys is not None
        relevant = relevant or any(
            attr in validated_data and getattr(instance, attr) != value
            for attr, value in validated_data.items()
            if attr in {'hostname', 'username', 'node'}
        )
        if apps is not None:
            relevant = relevant or set(instance.service_plan.apps.all()) != set(apps)
        if plan is not None:
            plan_fields = [f.name for f in models.PlanBase._meta.fields if f.name != 'id']
            relevant = relevant or instance.service_plan.name != plan.name or any(
                getattr(instance.service_plan, field) != getattr(plan, field)
                for field in plan_fields
            )
        if template is not None:
            relevant = relevant or instance.service_plan.template_id != template.id

        with transaction.atomic():
            if relevant:
                if not models.Service.claim_operation(instance.pk):
                    raise ServiceOperationConflict()
                # claim_operation updates the DB row; mirror it in memory so
                # the full-field save below does not write the flag back to False
                instance.operation_in_progress = True
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if apps is not None:
                instance.service_plan.apps.set(apps)
            if plan is not None:
                for field in plan_fields:
                    setattr(instance.service_plan, field, getattr(plan, field))
                instance.service_plan.name = plan.name
            if template is not None:
                instance.service_plan.template = template
                instance.service_plan.type = template.type
            if plan is not None or template is not None:
                instance.service_plan.save()

            if relevant:
                service_id = instance.id

                def dispatch():
                    try:
                        provision_service.delay(service_id, password, ssh_keys=ssh_keys)
                    except Exception:
                        models.Service.objects.filter(pk=service_id).update(
                            operation_in_progress=False,
                        )
                        raise

                transaction.on_commit(dispatch)
        return instance

    def validate(self, attrs):
        plan = attrs.get("plan")
        template = attrs.get("template")
        apps = attrs.get("apps", [])
        if template and plan:
            # Validate minimum resource requirements for selected apps
            for app in apps:
                if app.min_cores and plan.cores < app.min_cores:
                    raise serializers.ValidationError(
                        {"apps": f"App '{app.name}' requires at least {app.min_cores} cores."}
                    )
                if app.min_ram and plan.ram < app.min_ram:
                    raise serializers.ValidationError(
                        {"apps": f"App '{app.name}' requires at least {app.min_ram} MB RAM."}
                    )
                if app.min_disk and plan.size < app.min_disk:
                    raise serializers.ValidationError(
                        {"apps": f"App '{app.name}' requires at least {app.min_disk} GB disk."}
                    )
        return attrs

    def create(self, validated_data):
        request = self.context.get('request', None)
        plan = validated_data.pop("plan")
        password = validated_data.pop("password", None)
        template = validated_data.pop("template", None)
        apps = validated_data.pop("apps", [])
        ssh_keys = validated_data.pop("ssh_keys", None)

        with transaction.atomic():
            # Snapshot plan fields into ServicePlan
            plan_fields = [f.name for f in models.PlanBase._meta.fields if f.name != "id"]
            plan_values = dict([(x, getattr(plan, x)) for x in plan_fields])
            plan_values['name'] = plan.name
            sps = ServicePlanSerializer()
            service_plan = sps.create(plan_values)

            if "owner" not in validated_data:
                validated_data["owner"] = request.user
            # node may be present-but-None (the admin serializer lists it as a
            # writable field), so select from inventory whenever it's unset.
            if not validated_data.get("node"):
                inventory = (
                    models.Inventory.objects.select_for_update()
                    .filter(plan=plan, quantity__gt=0)
                    .first()
                )
                if not inventory:
                    raise serializers.ValidationError({"plan": "No available capacity for this plan."})
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

        # IP assignment happens inside provision_service task (outside transaction)
        service_id = service.id
        service_password = password
        transaction.on_commit(
            lambda: provision_service.delay(
                service_id, service_password, ssh_keys=ssh_keys
            )
        )
        return service


class ServiceSerializerClient(ServiceSerializer):
    service_plan = ServicePlanSerializerClient(read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['hostname', 'password', 'plan', 'template', 'apps', 'ssh_keys', 'username']:
                self.fields[field].read_only = True


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Inventory
        fields = '__all__'


class InventorySerializerClient(serializers.ModelSerializer):
    class Meta:
        model = models.Inventory
        fields = ('id', 'plan', 'quantity')
        read_only_fields = fields


class IPSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.IP
        fields = '__all__'

class AppProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AppProfile
        fields = '__all__'


class AppProfileSerializerClient(serializers.ModelSerializer):
    class Meta:
        model = models.AppProfile
        fields = ('id', 'name', 'description', 'min_cores', 'min_ram', 'min_disk', 'created')
        read_only_fields = fields


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Template
        fields = '__all__'
        read_only_fields = ('status', 'status_msg')

    def create(self, validated_data):
        template = super().create(validated_data)
        # Creating a KVM template from a cloud image URL kicks off an async import.
        if template.type == 'kvm' and template.source_url:
            template.status = 'pending'
            template.save(update_fields=['status'])
            from .tasks import import_kvm_template
            import_kvm_template.delay(template.id)
        return template


class TemplateSerializerClient(serializers.ModelSerializer):
    class Meta:
        model = models.Template
        fields = ('id', 'name', 'type', 'status', 'created')
        read_only_fields = fields


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

    def validate_external_port(self, value):
        if not 1 <= value <= 65535:
            raise serializers.ValidationError("external_port must be between 1 and 65535.")
        return value

    MAX_FORWARDS_PER_BLOCK = 50

    def validate(self, attrs):
        port_block = attrs.get('port_block') or (self.instance.port_block if self.instance else None)
        external_port = attrs.get('external_port', getattr(self.instance, 'external_port', None))
        if port_block and external_port is not None:
            if not (port_block.port_start <= external_port <= port_block.port_end):
                raise serializers.ValidationError({
                    'external_port': f"Must be within port block range {port_block.port_start}-{port_block.port_end}."
                })
        # Limit port forwards per block
        if port_block and not self.instance:
            current_count = models.PortForward.objects.filter(port_block=port_block).count()
            if current_count >= self.MAX_FORWARDS_PER_BLOCK:
                raise serializers.ValidationError(
                    f"Maximum of {self.MAX_FORWARDS_PER_BLOCK} port forwards per block reached."
                )
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

    def validate_port_block(self, value):
        request = self.context.get('request')
        if request and not request.user.is_staff:
            if value.service_network.service.owner != request.user:
                raise serializers.ValidationError("You do not own this port block's service.")
        return value


class DomainRouteSerializer(serializers.ModelSerializer):
    MAX_ROUTES_PER_SERVICE = 20

    verification_record_name = serializers.SerializerMethodField()
    verification_record_value = serializers.SerializerMethodField()

    class Meta:
        model = models.DomainRoute
        fields = '__all__'
        read_only_fields = ('npm_proxy_host_id', 'verification_status', 'verified_at')

    def get_verification_record_name(self, obj):
        if not obj.domain:
            return None
        return verification_record_name(obj.domain)

    def _is_owner_or_staff(self, obj):
        request = self.context.get('request')
        if not request or not getattr(request, 'user', None):
            return False
        user = request.user
        if getattr(user, 'is_staff', False):
            return True
        return bool(obj.service_id) and obj.service.owner_id == user.id

    def get_verification_record_value(self, obj):
        # The token is per-account; never leak another tenant's token. Only the
        # route's owner (or staff) may see the value they need to publish.
        if not self._is_owner_or_staff(obj):
            return None
        return account_token(obj.service.owner_id)

    def validate_forward_port(self, value):
        if not 1 <= value <= 65535:
            raise serializers.ValidationError("forward_port must be between 1 and 65535.")
        return value

    def validate_domain(self, value):
        value = (value or '').strip().lower()

        # Reuse the same character-class rules ServiceSerializer applies to
        # Service.hostname, plus a couple of DomainRoute-specific
        # requirements: a domain route is a public FQDN (must contain a dot),
        # not a bare hostname.
        if (
            not value
            or len(value) > 253
            or '.' not in value
            or not ServiceSerializer.hostname_pattern.match(value)
        ):
            raise serializers.ValidationError(
                "Domain must be a well-formed fully-qualified domain name (e.g. app.example.com)."
            )

        # Reserved/base domains the provider itself uses (e.g. its own portal
        # or infra vhosts) can never be claimed by a customer's domain route.
        # Configure via INVETERATE_RESERVED_DOMAINS (list of base domains;
        # exact matches and any subdomain of a reserved entry are blocked).
        # Defaults to empty so this is a no-op until the host project opts in
        # by setting the list to its own domain(s).
        reserved_domains = getattr(settings, "INVETERATE_RESERVED_DOMAINS", ())
        for reserved in reserved_domains:
            reserved = (reserved or '').strip().lower().lstrip('.')
            if not reserved:
                continue
            if value == reserved or value.endswith('.' + reserved):
                raise serializers.ValidationError(
                    f"The domain '{value}' is reserved and cannot be used for a customer domain route."
                )

        # TODO: this only blocks domains under the provider's own reserved
        # base domain(s) above. It does NOT verify that the requesting
        # customer actually controls `value` for domains outside that list --
        # nothing stops one customer from pointing a route at a domain owned
        # by another customer (or any third party). Real DNS-ownership
        # verification (e.g. a TXT-record challenge that must be satisfied
        # before the route is activated / before Let's Encrypt is attempted
        # via sync_domain_route) is a separate, larger feature and is still
        # required before this endpoint is safe for arbitrary customer-
        # supplied domains.
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
            # Limit domain routes per service
            if not self.instance:
                current_count = models.DomainRoute.objects.filter(service=service).count()
                if current_count >= self.MAX_ROUTES_PER_SERVICE:
                    raise serializers.ValidationError(
                        f"Maximum of {self.MAX_ROUTES_PER_SERVICE} domain routes per service reached."
                    )
        return attrs

    def create(self, validated_data):
        # A new route starts inert (pending): NPM sync (and thus the LE
        # attempt) is gated on the TXT challenge. The first verify attempt
        # usually fails immediately -- expected; the user then adds the record
        # and re-triggers via the /verify action.
        instance = super().create(validated_data)
        verify_domain_route.delay(instance.id)
        return instance

    def update(self, instance, validated_data):
        old_domain = instance.domain
        new_domain = validated_data.get('domain', old_domain)
        domain_changed = new_domain != old_domain

        if domain_changed:
            validated_data['verification_status'] = models.DomainRoute.VerificationStatus.PENDING
            validated_data['verified_at'] = None

        instance = super().update(instance, validated_data)

        if domain_changed:
            # New domain must be re-proven before it activates.
            verify_domain_route.delay(instance.id)
        elif instance.verification_status == models.DomainRoute.VerificationStatus.VERIFIED:
            # Same, already-verified domain (e.g. forward_port change) -> the
            # ownership proof still holds, so re-sync directly.
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

    def validate_service(self, value):
        request = self.context.get('request')
        if request and not request.user.is_staff:
            if value.owner != request.user:
                raise serializers.ValidationError("You do not own this service.")
        return value
