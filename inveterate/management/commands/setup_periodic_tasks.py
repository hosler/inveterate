from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


TASKS = [
    {
        'name': 'Calculate Inventory',
        'task': 'inveterate.tasks.calculate_inventory',
        'every': 10,
        'period': IntervalSchedule.MINUTES,
    },
    {
        'name': 'Meter Bandwidth',
        'task': 'inveterate.tasks.meter_bandwidth',
        'every': 5,
        'period': IntervalSchedule.MINUTES,
    },
    {
        'name': 'Cleanup Console Users',
        'task': 'inveterate.tasks.cleanup_console_users',
        'every': 1,
        'period': IntervalSchedule.HOURS,
    },
    {
        'name': 'Cleanup Orphaned IPs',
        'task': 'inveterate.tasks.cleanup_orphaned_ips',
        'every': 1,
        'period': IntervalSchedule.HOURS,
    },
    {
        'name': 'Sync LXC Templates',
        'task': 'inveterate.tasks.sync_templates',
        'every': 6,
        'period': IntervalSchedule.HOURS,
    },
    {
        'name': 'Sync KVM Templates',
        'task': 'inveterate.tasks.sync_kvm_templates',
        'every': 6,
        'period': IntervalSchedule.HOURS,
    },
]


class Command(BaseCommand):
    help = "Create or update periodic Celery Beat tasks for Inveterate."

    def handle(self, *args, **options):
        for entry in TASKS:
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=entry['every'],
                period=entry['period'],
            )
            _, created = PeriodicTask.objects.update_or_create(
                name=entry['name'],
                defaults={
                    'task': entry['task'],
                    'interval': schedule,
                    'enabled': True,
                },
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(f"{verb} task '{entry['name']}' (every {entry['every']} {entry['period']})")
