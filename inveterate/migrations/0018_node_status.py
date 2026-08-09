from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inveterate', '0017_domainroute_verification_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='node',
            name='status',
            field=models.CharField(
                choices=[
                    ('online', 'Online'),
                    ('offline', 'Offline'),
                    ('unknown', 'Unknown'),
                ],
                default='unknown',
                max_length=16,
            ),
        ),
    ]
