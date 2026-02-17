# RKC: Migration for dynamic workflow email fields (v1.2.0)
# Adds from_address, cc, bcc, and error_tag to WorkflowActionEmail

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "1074_workflowrun_deleted_at_workflowrun_restored_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowactionemail",
            name="from_address",
            field=models.CharField(
                blank=True,
                help_text="Override the sender address. Supports Jinja2 templates. Falls back to mail account from_address or username if empty.",
                max_length=256,
                null=True,
                verbose_name="from email address",
            ),
        ),
        migrations.AddField(
            model_name="workflowactionemail",
            name="cc",
            field=models.TextField(
                blank=True,
                help_text="CC email addresses, comma separated. Supports Jinja2 templates with custom field placeholders.",
                null=True,
                verbose_name="emails cc",
            ),
        ),
        migrations.AddField(
            model_name="workflowactionemail",
            name="bcc",
            field=models.TextField(
                blank=True,
                help_text="BCC email addresses, comma separated. Supports Jinja2 templates with custom field placeholders.",
                null=True,
                verbose_name="emails bcc",
            ),
        ),
        migrations.AddField(
            model_name="workflowactionemail",
            name="error_tag",
            field=models.ForeignKey(
                blank=True,
                help_text="Tag to apply to the document if email sending fails due to validation errors (e.g. invalid rendered email address).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="documents.tag",
                verbose_name="error tag",
            ),
        ),
    ]
