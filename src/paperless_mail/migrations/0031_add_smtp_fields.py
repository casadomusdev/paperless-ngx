# RKC: SMTP email sending refactor (v1.1.0)
# Generated manually on 2026-01-28
# Adds SMTP server configuration fields and updates use_for_sending to support both OAuth2 and traditional SMTP

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless_mail", "0030_add_oauth_sending_fields"),
    ]

    operations = [
        # Update help text for existing use_for_sending field
        migrations.AlterField(
            model_name="mailaccount",
            name="use_for_sending",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Allow this account to be used for sending outgoing emails. "
                    "Only one account can be enabled for sending at a time."
                ),
                verbose_name="use for sending",
            ),
        ),
        # Add SMTP server configuration fields
        migrations.AddField(
            model_name="mailaccount",
            name="smtp_server",
            field=models.CharField(
                blank=True,
                help_text=(
                    "SMTP server hostname for sending emails. "
                    "If not set, defaults will be used based on account type."
                ),
                max_length=256,
                null=True,
                verbose_name="SMTP server",
            ),
        ),
        migrations.AddField(
            model_name="mailaccount",
            name="smtp_port",
            field=models.IntegerField(
                blank=True,
                help_text=(
                    "SMTP server port. Common values: 587 (STARTTLS), 465 (SSL), 25 (unencrypted)."
                ),
                null=True,
                verbose_name="SMTP port",
            ),
        ),
        migrations.AddField(
            model_name="mailaccount",
            name="smtp_security",
            field=models.CharField(
                blank=True,
                choices=[
                    ("SSL", "SSL"),
                    ("STARTTLS", "STARTTLS"),
                    ("NONE", "None"),
                ],
                help_text="SMTP security protocol.",
                max_length=10,
                null=True,
                verbose_name="SMTP security",
            ),
        ),
        migrations.AddField(
            model_name="mailaccount",
            name="smtp_username",
            field=models.CharField(
                blank=True,
                help_text=(
                    "SMTP username for traditional authentication. "
                    "Leave blank to use the same username as IMAP."
                ),
                max_length=256,
                null=True,
                verbose_name="SMTP username",
            ),
        ),
        migrations.AddField(
            model_name="mailaccount",
            name="smtp_password",
            field=models.CharField(
                blank=True,
                help_text=(
                    "SMTP password for traditional authentication. "
                    "Only used for non-OAuth accounts."
                ),
                max_length=2048,
                null=True,
                verbose_name="SMTP password",
            ),
        ),
    ]
