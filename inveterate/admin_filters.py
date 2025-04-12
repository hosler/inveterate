from django.contrib import admin
from django.utils.translation import gettext_lazy as _

class ResourceUsageFilter(admin.SimpleListFilter):
    title = _('Resource Usage')
    parameter_name = 'resource_usage'

    def lookups(self, request, model_admin):
        return (
            ('high', _('High (>80%)')),
            ('medium', _('Medium (40-80%)')),
            ('low', _('Low (<40%)')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'high':
            return queryset.filter(usage__gt=80)
        if self.value() == 'medium':
            return queryset.filter(usage__gte=40, usage__lte=80)
        if self.value() == 'low':
            return queryset.filter(usage__lt=40)

class StatusFilter(admin.SimpleListFilter):
    title = _('Status')
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('active', _('Active')),
            ('pending', _('Pending')),
            ('error', _('Error')),
            ('suspended', _('Suspended')),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
