# Generated by Django 5.0.6 on 2025-03-19 16:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('csdata', '0005_alter_employee_address_alter_employee_email_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='profile_image',
            field=models.URLField(),
        ),
    ]
