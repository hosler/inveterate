from django.db import migrations
import inveterate.fields


class Migration(migrations.Migration):

    dependencies = [
        ("inveterate", "0011_service_username"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cluster",
            name="key",
            field=inveterate.fields.EncryptedCharField(max_length=255),
        ),
        migrations.AlterField(
            model_name="portgateway",
            name="admin_password",
            field=inveterate.fields.EncryptedCharField(max_length=255),
        ),
    ]
