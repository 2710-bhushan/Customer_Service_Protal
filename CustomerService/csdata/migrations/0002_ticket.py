# Generated by Django 5.0.6 on 2025-03-19 14:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('csdata', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('unique', models.AutoField(primary_key=True, serialize=False)),
                ('mail', models.CharField(max_length=70)),
                ('phone', models.IntegerField(max_length=13)),
                ('ticketdetail', models.TextField(max_length=1500)),
            ],
        ),
    ]
