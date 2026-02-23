import os

from django.core.management.base import BaseCommand

from inveterate.models import Cluster


class Command(BaseCommand):
    help = "Create or update the default cluster from environment variables."

    def handle(self, *args, **options):
        name = os.environ.get("PROXMOX_CLUSTER_NAME", "default")
        host = os.environ.get("PROXMOX_HOST")
        user = os.environ.get("PROXMOX_USER")
        key = os.environ.get("PROXMOX_KEY")

        if not all([host, user, key]):
            self.stdout.write(
                "Skipping cluster init — set PROXMOX_HOST, PROXMOX_USER, "
                "and PROXMOX_KEY to enable."
            )
            return

        cluster, created = Cluster.objects.update_or_create(
            name=name,
            defaults={"host": host, "user": user, "key": key},
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(f"{verb} cluster '{cluster.name}' → {cluster.host}")
