# Generated by Django 5.0.6 on 2025-04-01 12:56

import csdata.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('csdata', '0017_alter_cdetail_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='passw',
            field=models.CharField(default=csdata.models.get_default_servic, max_length=30),
        ),
    ]
