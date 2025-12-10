# RKC: OAuth2 email sending support (v1.0.18)
# Generated manually on 2025-01-12

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("paperless_mail", "0029_mailrule_pdf_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="mailaccount",
            name="use_for_sending",
            field=models.BooleanField(
                default=False,
                help_text="Allow this account to be used for sending outgoing emails via OAuth2.",
                verbose_name="use for sending",
            ),
        ),
        migrations.AddField(
            model_name="mailaccount",
            name="from_address",
            field=models.EmailField(
                blank=True,
                help_text=(
                    "The email address to use as sender when sending emails. "
                    "If not set, will use the username if it's an email address."
                ),
                max_length=254,
                null=True,
                verbose_name="from address",
            ),
        ),
    ]
