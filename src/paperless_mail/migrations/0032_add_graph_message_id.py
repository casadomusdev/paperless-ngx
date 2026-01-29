# RKC: Graph API mail retrieval support (v1.1.0)
# Generated manually on 2026-01-29
# Adds graph_message_id field to store full Microsoft Graph API message IDs
# while keeping uid as 8-character hash for display

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless_mail", "0031_add_smtp_fields"),
    ]

    operations = [
        # Update help text for existing uid field
        migrations.AlterField(
            model_name="processedmail",
            name="uid",
            field=models.CharField(
                editable=False,
                help_text="Message UID: numeric for IMAP, 8-character hash for Graph API",
                max_length=256,
                verbose_name="uid",
            ),
        ),
        # Add graph_message_id field for full Graph API message IDs
        migrations.AddField(
            model_name="processedmail",
            name="graph_message_id",
            field=models.TextField(
                blank=True,
                editable=False,
                help_text=(
                    "Full Microsoft Graph API message ID. Only populated for Outlook OAuth accounts. "
                    "Required for batch post-action processing (mark read, delete, etc.)."
                ),
                null=True,
                verbose_name="graph message id",
            ),
        ),
    ]
