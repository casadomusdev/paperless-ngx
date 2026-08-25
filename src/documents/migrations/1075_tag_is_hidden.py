# RKC: Hidden tags — suppress badge rendering in document list views (v1.6.0)

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1074_workflowrun_deleted_at_workflowrun_restored_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tag",
            name="is_hidden",
            field=models.BooleanField(
                default=False,
                help_text="Marks this tag as hidden: the tag remains assigned to documents but its badge is not shown in list views.",
                verbose_name="is hidden",
            ),
        ),
    ]
