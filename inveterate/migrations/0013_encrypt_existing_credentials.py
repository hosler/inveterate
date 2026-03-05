"""Data migration: re-save existing Cluster and PortGateway rows so that
plaintext credential values are encrypted at rest by django-cryptography."""

from django.db import migrations


def encrypt_existing(apps, schema_editor):
    Cluster = apps.get_model("inveterate", "Cluster")
    for cluster in Cluster.objects.all():
        cluster.save(update_fields=["key"])

    PortGateway = apps.get_model("inveterate", "PortGateway")
    for gw in PortGateway.objects.all():
        gw.save(update_fields=["admin_password"])


class Migration(migrations.Migration):

    dependencies = [
        ("inveterate", "0012_encrypt_credentials"),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
    ]
