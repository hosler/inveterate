# Generated migration to encrypt Cluster API tokens
from django.db import migrations
import fernet_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('inveterate', '0002_remove_node_maintenance_mode_remove_node_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cluster',
            name='key',
            field=fernet_fields.fields.EncryptedCharField(max_length=255),
        ),
    ]
