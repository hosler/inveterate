from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("inveterate", "0018_node_status")]

    operations = [
        migrations.AddField(
            model_name="service",
            name="operation_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="DriftFinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("ghost-service", "Ghost service"), ("orphan-vm", "Orphan VM"), ("config-drift", "Configuration drift"), ("power-drift", "Power drift"), ("stuck-operation", "Stuck operation"), ("stuck-pending", "Stuck pending service"), ("stranded-ip", "Stranded IP"), ("stranded-npm", "Stranded NPM resource"), ("unsynced-domain", "Unsynced domain"), ("paying-no-service", "Paying subscription without service"), ("service-no-billing", "Service without billing"), ("price-drift", "Price drift"), ("zombie-order", "Zombie order")], max_length=64)),
                ("severity", models.CharField(choices=[("critical", "Critical"), ("warning", "Warning")], max_length=16)),
                ("fingerprint", models.CharField(max_length=255, unique=True)),
                ("details", models.JSONField()),
                ("first_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-last_seen"]},
        ),
    ]
