# RKC: Migration for PendingEmail model (v1.5.0)
# Email send queue with retry for transient failures.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "1075_workflowactionemail_dynamic_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PendingEmail",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject_template", models.TextField(default="", verbose_name="email subject")),
                ("body_template", models.TextField(default="", verbose_name="email body")),
                ("to_template", models.TextField(default="", verbose_name="email to")),
                ("from_template", models.TextField(blank=True, default="", verbose_name="email from")),
                ("cc_template", models.TextField(blank=True, default="", verbose_name="email cc")),
                ("bcc_template", models.TextField(blank=True, default="", verbose_name="email bcc")),
                ("is_html", models.BooleanField(default=False, verbose_name="is HTML")),
                ("include_document", models.BooleanField(default=True, verbose_name="include document")),
                ("rendered_to", models.TextField(default="", verbose_name="rendered to")),
                ("attempts", models.PositiveIntegerField(default=0, verbose_name="attempts")),
                ("max_attempts", models.PositiveIntegerField(default=50, verbose_name="max attempts")),
                ("next_retry_at", models.DateTimeField(verbose_name="next retry at")),
                ("last_error", models.TextField(blank=True, default="", verbose_name="last error")),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("SENDING", "Sending"), ("SENT", "Sent"), ("ABANDONED", "Abandoned")], default="PENDING", max_length=20, verbose_name="status")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="updated at")),
                ("action", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="documents.workflowactionemail", verbose_name="workflow action")),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="documents.document", verbose_name="document")),
            ],
            options={
                "verbose_name": "pending email",
                "verbose_name_plural": "pending emails",
                "ordering": ["next_retry_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pendingemail",
            index=models.Index(fields=["status", "next_retry_at"], name="idx_pending_email_status_retry"),
        ),
    ]
