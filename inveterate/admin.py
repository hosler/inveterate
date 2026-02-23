from django import forms
from django.contrib import admin
from django.utils.html import format_html
from . import models

class NodeDiskInline(admin.TabularInline):
    model = models.NodeDisk
    extra = 1
    fields = ('name', 'size', 'primary', 'shared')

class ServiceNetworkInline(admin.TabularInline):
    model = models.ServiceNetwork
    extra = 1
    readonly_fields = ('net_id',)
    fields = ('net_id', 'ip')

class AppProfileForm(forms.ModelForm):
    class Meta:
        model = models.AppProfile
        fields = '__all__'
        widgets = {
            'cloud_init': forms.Textarea(attrs={'rows': 20, 'cols': 80}),
        }


@admin.register(models.AppProfile)
class AppProfileAdmin(admin.ModelAdmin):
    form = AppProfileForm
    list_display = ('name', 'created')
    search_fields = ('name', 'description')
    readonly_fields = ('created', 'updated')


@admin.register(models.Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('name', 'host', 'user', 'node_count', 'created', 'updated')
    search_fields = ('name', 'host')
    readonly_fields = ('created', 'updated')
    actions = ['test_connection', 'sync_nodes']

    def node_count(self, obj):
        return models.Node.objects.filter(cluster=obj).count()
    node_count.short_description = 'Nodes'

    def test_connection(self, request, queryset):
        for cluster in queryset:
            try:
                from .tasks import get_cluster_resources
                get_cluster_resources.delay(cluster.id)
                self.message_user(request, f"Successfully connected to {cluster.name}")
            except Exception as e:
                self.message_user(request, f"Failed to connect to {cluster.name}: {str(e)}", level='ERROR')
    test_connection.short_description = "Test cluster connection"

@admin.register(models.Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'cluster', 'cores', 'ram', 'size', 'service_count', 'created')
    list_filter = ('cluster',)
    search_fields = ('name',)
    inlines = [NodeDiskInline]
    readonly_fields = ('created', 'updated')

    def service_count(self, obj):
        return obj.services.count()
    service_count.short_description = 'Services'

@admin.register(models.Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'file', 'status', 'node', 'created')
    list_filter = ('type', 'status')
    search_fields = ('name', 'file', 'source_url')
    readonly_fields = ('created', 'updated')
    fieldsets = (
        (None, {
            'fields': ('name', 'type', 'file'),
        }),
        ('Cloud Image Import', {
            'classes': ('collapse',),
            'fields': ('source_url', 'node', 'status', 'status_msg'),
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
        }),
    )
    actions = ['import_kvm_templates']

    def import_kvm_templates(self, request, queryset):
        from .tasks import import_kvm_template
        count = 0
        for template in queryset.filter(type='kvm').exclude(source_url=''):
            template.file = ''
            template.status = 'pending'
            template.status_msg = ''
            template.save()
            import_kvm_template.delay(template.id)
            count += 1
        self.message_user(request, f"Queued {count} KVM template(s) for import")
    import_kvm_templates.short_description = "Import selected KVM cloud image templates"

@admin.register(models.Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'size', 'ram', 'cores', 'bandwidth', 'created')
    search_fields = ('name',)
    readonly_fields = ('created', 'updated')

@admin.register(models.IPPool)
class IPPoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'network', 'mask', 'gateway', 'internal', 'ip_count', 'created')
    list_filter = ('type', 'internal')
    search_fields = ('name', 'network')
    filter_horizontal = ('nodes',)
    readonly_fields = ('created', 'updated')

    def ip_count(self, obj):
        return models.IP.objects.filter(pool=obj).count()
    ip_count.short_description = 'Total IPs'

@admin.register(models.IP)
class IPAdmin(admin.ModelAdmin):
    list_display = ('value', 'pool', 'owner', 'created')
    list_filter = ('pool',)
    search_fields = ('value',)
    readonly_fields = ('created', 'updated')

@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'owner', 'plan_name', 'node', 'status', 'created')
    list_filter = ('status', 'node')
    search_fields = ('hostname', 'owner__username')
    readonly_fields = ('created', 'updated', 'machine_id', 'bw_usage', 'bw_banked', 'bw_stale', 'bw_system_tick', 'bw_renewal_dtm')
    inlines = [ServiceNetworkInline]
    actions = ['start_service', 'stop_service', 'provision_service']

    def plan_name(self, obj):
        return obj.service_plan.name if obj.service_plan else '-'
    plan_name.short_description = 'Plan'

    def start_service(self, request, queryset):
        for service in queryset:
            from .tasks import start_vm
            start_vm.delay(service.id)
        self.message_user(request, f"Started {queryset.count()} services")
    start_service.short_description = "Start selected services"

    def stop_service(self, request, queryset):
        for service in queryset:
            from .tasks import stop_vm
            stop_vm.delay(service.id)
        self.message_user(request, f"Stopped {queryset.count()} services")
    stop_service.short_description = "Stop selected services"

@admin.register(models.ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'size', 'ram', 'cores', 'created')
    list_filter = ('type',)
    readonly_fields = ('created', 'updated')

