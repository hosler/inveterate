from django.apps import AppConfig


class InveterateConfig(AppConfig):
    name = 'inveterate'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Inveterate Proxmox Management'

    def ready(self):
        """
        Perform initialization when Django starts.
        Import signal handlers, schedule periodic tasks, etc.
        """
        # Import tasks to ensure they're registered with Celery
        from . import tasks  # noqa
