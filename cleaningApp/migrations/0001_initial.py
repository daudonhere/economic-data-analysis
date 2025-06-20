# Generated by Django 5.2.1 on 2025-05-29 14:46

import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CleaningData',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('content', models.JSONField()),
                ('source', models.URLField()),
                ('createdAt', models.DateTimeField(default=django.utils.timezone.now)),
                ('updatedAt', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'tb_cleaning_data',
            },
        ),
    ]
