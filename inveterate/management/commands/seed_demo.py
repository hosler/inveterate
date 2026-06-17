"""Populate a fresh install with a demo catalog.

Creates a few plans, OS templates, and app profiles so the API and admin are
not empty on first boot. Idempotent — safe to run on every container start.
Does NOT touch Proxmox; use `manage.py init_cluster` (with PROXMOX_* env vars)
to attach real hardware.
"""
from django.core.management.base import BaseCommand

from inveterate.models import AppProfile, Plan, Template

PLANS = [
    # name,        size, ram,  swap, cores, bandwidth, price
    ("Nano",        20,  1024, 1024, 1,     1000,      5.00),
    ("Small",       40,  2048, 2048, 2,     2000,      10.00),
    ("Medium",      80,  4096, 4096, 4,     4000,      20.00),
]

TEMPLATES = [
    ("Ubuntu 24.04", "kvm"),
    ("Debian 12", "kvm"),
    ("Rocky Linux 9", "kvm"),
]

APP_PROFILES = [
    (
        "Docker",
        "#cloud-config\npackages:\n  - docker.io\nruncmd:\n  - systemctl enable --now docker\n",
        1, 1024, 10,
    ),
    (
        "Nginx",
        "#cloud-config\npackages:\n  - nginx\nruncmd:\n  - systemctl enable --now nginx\n",
        1, 512, 5,
    ),
]


class Command(BaseCommand):
    help = "Seed a demo catalog (plans, templates, app profiles). Idempotent."

    def handle(self, *args, **options):
        for name, size, ram, swap, cores, bandwidth, price in PLANS:
            _, created = Plan.objects.update_or_create(
                name=name,
                defaults={
                    "size": size,
                    "ram": ram,
                    "swap": swap,
                    "cores": cores,
                    "bandwidth": bandwidth,
                    "internal_ips": 1,
                    "monthly_price": price,
                    "annual_price": round(price * 10, 2),
                },
            )
            self.stdout.write(f"{'+ ' if created else '= '}plan {name}")

        for name, vm_type in TEMPLATES:
            _, created = Template.objects.update_or_create(
                name=name,
                defaults={"type": vm_type, "status": "ready"},
            )
            self.stdout.write(f"{'+ ' if created else '= '}template {name}")

        for name, cloud_init, min_cores, min_ram, min_disk in APP_PROFILES:
            _, created = AppProfile.objects.update_or_create(
                name=name,
                defaults={
                    "cloud_init": cloud_init,
                    "min_cores": min_cores,
                    "min_ram": min_ram,
                    "min_disk": min_disk,
                },
            )
            self.stdout.write(f"{'+ ' if created else '= '}app profile {name}")

        self.stdout.write(self.style.SUCCESS("Demo catalog ready."))
