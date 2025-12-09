# RKC: Migration to add global saved views ordering fields to ApplicationConfiguration
# Generated manually on 2025-01-09

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless", "0004_applicationconfiguration_barcode_asn_prefix_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicationconfiguration",
            name="global_sidebar_views_order",
            field=models.JSONField(
                blank=True,
                help_text="Array of saved view IDs defining the sidebar order for global views",
                null=True,
                verbose_name="Global saved views sidebar order",
            ),
        ),
        migrations.AddField(
            model_name="applicationconfiguration",
            name="global_dashboard_views_order",
            field=models.JSONField(
                blank=True,
                help_text="Array of saved view IDs defining the dashboard order for global views",
                null=True,
                verbose_name="Global saved views dashboard order",
            ),
        ),
    ]
