from django.db import models
from django.contrib.auth import get_user_model

# Get the UserModel
UserModel = get_user_model()

VM_TYPES = (
    ("lxc", "LXC"),
    ("kvm", "KVM")
)


class Config(models.Model):
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class BillingType(models.Model):
    BILLING_CHOICES = (
        ("blesta", "Blesta"),
        ("stripe", "Stripe"),
    )
    type = models.CharField(max_length=255, default="stripe", choices=BILLING_CHOICES)
    name = models.CharField(max_length=255)
    mirror = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class BlestaBackend(models.Model):
    billing_type = models.OneToOneField(BillingType, on_delete=models.CASCADE, related_name="backend")
    host = models.CharField(max_length=255, null=True)
    user = models.CharField(max_length=255, null=True)
    key = models.CharField(max_length=255, null=True)
    company_hostname = models.CharField(max_length=255, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.billing_type


class Template(models.Model):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255, default="lxc", choices=VM_TYPES)
    file = models.CharField(max_length=255)
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
    dns = models.GenericIPAddressField()
    nodes = models.ManyToManyField("Node")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class PlanBase(models.Model):
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
    ip_pools = models.ManyToManyField(IPPool)


class Plan(PlanBase):
    name = models.CharField(max_length=255)
    price = models.FloatField(default=0.0)
    term = models.IntegerField(default='1')
    period = models.CharField(default='monthly', max_length=255)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class Cluster(models.Model):
    NODE_CHOICES = (
        ("proxmox", "Proxmox"),
    )
    name = models.CharField(max_length=255)
    host = models.CharField(max_length=255)
    user = models.CharField(max_length=255)
    key = models.CharField(max_length=255)
    type = models.CharField(max_length=255, default="proxmox", choices=NODE_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name


class Node(PlanBase):
    NODE_CHOICES = (
        ("proxmox", "Proxmox"),
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255, default="proxmox", choices=NODE_CHOICES)
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
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"{self.name} ({self.node.name})"


class ServicePlan(PlanBase):
    type = models.CharField(max_length=255, choices=VM_TYPES)
    template = models.ForeignKey(Template, null=True, on_delete=models.SET_NULL)
    storage = models.ForeignKey(NodeDisk, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return str(self.id)


class ServiceBandwidth(models.Model):
    bandwidth = models.IntegerField(default=0)
    bandwidth_banked = models.IntegerField(default=0)
    bandwidth_stale = models.IntegerField(default=0)
    system_tick = models.IntegerField(default=0)
    renewal_dtm = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']


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
    plan = models.ForeignKey(Plan, null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=255, default='pending', choices=STATUS_CHOICES)
    status_msg = models.CharField(max_length=255, null=True, blank=True)
    hostname = models.CharField(max_length=255)
    billing_type = models.ForeignKey(BillingType, null=True, on_delete=models.SET_NULL)
    billing_id = models.CharField(max_length=255, null=True)
    machine_id = models.IntegerField(null=True, blank=True)
    node = models.ForeignKey(Node, null=True, on_delete=models.SET_NULL, related_name='services')
    service_plan = models.OneToOneField(ServicePlan, on_delete=models.SET_NULL, null=True, related_name='service')
    bandwidth = models.OneToOneField(ServiceBandwidth, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='service')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        if self.service_plan:
            self.service_plan.delete()
        if self.bandwidth:
            self.bandwidth.delete()

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


class ServiceDisk(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='service_disk')
    size = models.IntegerField()
    node = models.ForeignKey(Node, on_delete=models.CASCADE)
    file = models.CharField(null=True, max_length=255)
    primary = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']


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


class Domain(models.Model):
    name = models.CharField(null=False, max_length=255)
    ssl = models.BooleanField(default=False)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, related_name='domain', null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']


class Stream(models.Model):
    name = models.CharField(null=False, max_length=255)
    port = models.IntegerField(null=False)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, related_name='domain', null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']


class DashboardSummary(models.Model):
    user_count = models.IntegerField()
    plan_count = models.IntegerField()
    ip_count = models.IntegerField()
    template_count = models.IntegerField()
    service_count = models.IntegerField()
    node_count = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
