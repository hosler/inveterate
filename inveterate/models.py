from django.db import models
from django.contrib.auth import get_user_model

# Get the UserModel
UserModel = get_user_model()

VM_TYPES = (
    ("lxc", "LXC"),
    ("kvm", "KVM")
)


class Template(models.Model):
    TEMPLATE_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('importing', 'Importing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    )

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255, default="lxc", choices=VM_TYPES)
    file = models.CharField(max_length=255, blank=True, default='')
    source_url = models.URLField(max_length=1024, blank=True, default='')
    node = models.ForeignKey('Node', null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=32, choices=TEMPLATE_STATUS_CHOICES, default='ready')
    status_msg = models.CharField(max_length=512, blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class IPPool(models.Model):
    IP_CHOICES = (
        ("ipv4", "IPv4"),
        ("ipv6", "IPv6")
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255, default="ipv4", choices=IP_CHOICES)
    network = models.GenericIPAddressField()
    mask = models.IntegerField()
    gateway = models.GenericIPAddressField()
    internal = models.BooleanField(default=False)
    interface = models.CharField(max_length=255, default='vmbr0')
    vlan_tag = models.IntegerField(null=True, blank=True)
    dns = models.GenericIPAddressField()
    nodes = models.ManyToManyField("Node")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class PlanBase(models.Model):
    """Resource specification fields.

    On Plan/ServicePlan: per-service allocation.
    On Node: total node capacity limits.
    Shared field names enable the inventory calculation loop.
    """

    class Meta:
        abstract = True

    size = models.IntegerField(default=8)
    ram = models.IntegerField(default=16)
    swap = models.IntegerField(default=16)
    cores = models.IntegerField(default=1)
    bandwidth = models.IntegerField(default=1024)
    cpu_units = models.IntegerField(default=1024)
    cpu_limit = models.DecimalField(default=1.00, decimal_places=2, max_digits=3)
    ipv6_ips = models.IntegerField(default=0)
    ipv4_ips = models.IntegerField(default=0)
    internal_ips = models.IntegerField(default=0)



class Plan(PlanBase):
    name = models.CharField(max_length=255)
    monthly_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    annual_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class Cluster(models.Model):
    name = models.CharField(max_length=255)
    host = models.CharField(max_length=255)
    user = models.CharField(max_length=255)
    key = models.CharField(max_length=255)
    bandwidth = models.IntegerField(default=0, help_text="Monthly bandwidth budget in GB (0 = unlimited)")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class Node(PlanBase):
    name = models.CharField(max_length=255)
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class NodeDisk(models.Model):
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='node_disk')
    name = models.CharField(max_length=255, null=False)
    size = models.IntegerField()
    primary = models.BooleanField(default=True)
    shared = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(
                fields=['node', 'primary'],
                condition=models.Q(primary=True),
                name='unique_primary_per_node'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.node.name})"




class AppProfile(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    cloud_init = models.TextField()
    min_cores = models.PositiveIntegerField(default=0)
    min_ram = models.PositiveIntegerField(default=0)    # MB
    min_disk = models.PositiveIntegerField(default=0)   # GB
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class ServicePlan(PlanBase):
    name = models.CharField(max_length=255, default='')
    type = models.CharField(max_length=255, choices=VM_TYPES)
    template = models.ForeignKey(Template, null=True, on_delete=models.SET_NULL)
    storage = models.ForeignKey(NodeDisk, null=True, on_delete=models.SET_NULL)
    apps = models.ManyToManyField(AppProfile, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return str(self.id)


class Service(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('destroyed', 'Destroyed'),
        ('suspended', 'Suspended'),
        ('error', 'Error'),
        ('past_due', 'Past Due')
    )

    owner = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    status = models.CharField(max_length=255, default='pending', choices=STATUS_CHOICES)
    status_msg = models.CharField(max_length=255, null=True, blank=True)
    hostname = models.CharField(max_length=255)
    machine_id = models.IntegerField(null=True, blank=True)
    node = models.ForeignKey(Node, null=True, on_delete=models.SET_NULL, related_name='services')
    service_plan = models.OneToOneField(ServicePlan, on_delete=models.SET_NULL, null=True, related_name='service')
    bw_usage = models.BigIntegerField(default=0)
    bw_banked = models.BigIntegerField(default=0)
    bw_stale = models.BigIntegerField(default=0)
    bw_system_tick = models.IntegerField(default=0)
    bw_renewal_dtm = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        if self.service_plan:
            self.service_plan.delete()

    def __str__(self):
        return f"{self.id} ({self.hostname})"


class ServiceNetwork(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='service_network')
    net_id = models.IntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.net_id:
            net_devices = ServiceNetwork.objects.filter(service=self.service)
            if len(net_devices) > 0:
                for i, net_device in enumerate(net_devices):
                    if net_device.net_id != i:
                        self.net_id = i
                        return super().save(*args, **kwargs)
                self.net_id = len(net_devices)
            else:
                self.net_id = 0
        return super().save(*args, **kwargs)


class IP(models.Model):
    value = models.GenericIPAddressField(unique=True)
    pool = models.ForeignKey(IPPool, on_delete=models.CASCADE)
    owner = models.OneToOneField(ServiceNetwork, blank=True, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.value


class Inventory(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    node = models.ForeignKey(Node, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']


class PortGateway(models.Model):
    name = models.CharField(max_length=255)
    host = models.CharField(max_length=255)
    admin_email = models.EmailField()
    admin_password = models.CharField(max_length=255)
    port_range_start = models.IntegerField(default=10000)
    port_range_end = models.IntegerField(default=60000)
    block_size = models.IntegerField(default=100)
    pools = models.ManyToManyField('IPPool', blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class PortBlock(models.Model):
    gateway = models.ForeignKey(PortGateway, on_delete=models.CASCADE, related_name='port_blocks')
    service_network = models.OneToOneField(ServiceNetwork, on_delete=models.CASCADE, related_name='port_block')
    port_start = models.IntegerField()
    port_end = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(fields=['gateway', 'port_start'], name='unique_gateway_port_start')
        ]

    def __str__(self):
        return f"{self.gateway.name}:{self.port_start}-{self.port_end}"


PROTOCOL_CHOICES = (
    ('tcp', 'TCP'),
    ('udp', 'UDP'),
    ('both', 'TCP+UDP'),
)


class PortForward(models.Model):
    port_block = models.ForeignKey(PortBlock, on_delete=models.CASCADE, related_name='forwards')
    external_port = models.IntegerField()
    internal_port = models.IntegerField()
    protocol = models.CharField(max_length=4, choices=PROTOCOL_CHOICES, default='tcp')
    label = models.CharField(max_length=255, blank=True, default='')
    enabled = models.BooleanField(default=True)
    npm_stream_id = models.IntegerField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(
                fields=['port_block', 'external_port', 'protocol'],
                name='unique_portblock_extport_proto'
            )
        ]

    def __str__(self):
        return f"{self.external_port}->{self.internal_port}/{self.protocol}"


class DomainRoute(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='domain_routes')
    domain = models.CharField(max_length=255, unique=True)
    forward_port = models.IntegerField(default=80)
    ssl = models.BooleanField(default=True)
    force_ssl = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    npm_proxy_host_id = models.IntegerField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.domain


