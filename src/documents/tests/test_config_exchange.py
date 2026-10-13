# RKC: Tests for the configuration export / import feature.
# /end RKC edit
import json
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from documents.config_exchange.exporter import CONFIG_FILE_NAME
from documents.config_exchange.exporter import METADATA_FILE_NAME
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import DocumentType
from documents.models import SavedView
from documents.models import SavedViewFilterRule
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.settings import EXPORTER_CRYPTO_SETTINGS_NAME
from documents.tests.utils import DirectoriesMixin
from paperless.models import ApplicationConfiguration
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


class TestConfigExchange(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.target = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.target)
        self.user = User.objects.create(username="cfg_admin")

        self.parent_tag = Tag.objects.create(name="parent")
        # Tag uses django-treenode; the FK is tn_parent (parent is read-only)
        self.tag = Tag.objects.create(
            name="child",
            tn_parent=self.parent_tag,
            color="#112233",
        )
        self.doctype = DocumentType.objects.create(name="Invoice")
        self.correspondent = Correspondent.objects.create(name="ACME")
        self.storage_path = StoragePath.objects.create(
            name="By year",
            path="{created_year}/{title}",
        )
        self.custom_field = CustomField.objects.create(
            name="IBAN",
            data_type=CustomField.FieldDataType.STRING,
        )

        self.saved_view = SavedView.objects.create(
            name="Tagged child",
            show_on_dashboard=True,
            show_in_sidebar=True,
        )
        SavedViewFilterRule.objects.create(
            saved_view=self.saved_view,
            rule_type=6,
            value=str(self.tag.pk),
        )

        self.account = MailAccount.objects.create(
            name="Mailbox",
            imap_server="imap.example.com",
            username="user@example.com",
            password="topsecret",
        )
        self.mail_rule = MailRule.objects.create(
            name="From ACME",
            account=self.account,
            folder="INBOX",
        )
        self.mail_rule.assign_tags.add(self.tag)

        self.trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            sources=[str(WorkflowTrigger.DocumentSourceChoices.CONSUME_FOLDER.value)],
            filter_filename="*",
        )
        self.trigger.filter_has_tags.add(self.tag)
        self.action = WorkflowAction.objects.create(assign_title="new title")
        self.action.assign_tags.add(self.tag)
        self.workflow = Workflow.objects.create(name="Workflow 1", order=0)
        self.workflow.triggers.add(self.trigger)
        self.workflow.actions.add(self.action)

        # a post_save signal already creates UiSettings for new users
        UiSettings.objects.update_or_create(
            user=self.user,
            defaults={
                "settings": {
                    "permissions": {
                        "default_view_users": [self.user.pk],
                        "default_change_users": [],
                        "default_view_groups": [],
                        "default_change_groups": [],
                    },
                },
            },
        )
        config = ApplicationConfiguration.objects.first() or ApplicationConfiguration()
        config.app_title = "RKC Test"
        config.save()

    def _export(self, **kwargs) -> None:
        call_command("config_exporter", str(self.target), "--no-progress-bar", **kwargs)

    def _import(self, **kwargs) -> None:
        call_command("config_importer", str(self.target), "--no-progress-bar", **kwargs)

    def _wipe_config(self) -> None:
        SavedViewFilterRule.objects.all().delete()
        SavedView.objects.all().delete()
        Workflow.objects.all().delete()
        WorkflowAction.objects.all().delete()
        WorkflowTrigger.objects.all().delete()
        MailRule.objects.all().delete()
        MailAccount.objects.all().delete()
        StoragePath.objects.all().delete()
        CustomField.objects.all().delete()
        DocumentType.objects.all().delete()
        Correspondent.objects.all().delete()
        Tag.objects.all().delete()

    def test_export_writes_bundle(self) -> None:
        self._export()
        config = json.loads((self.target / CONFIG_FILE_NAME).read_text())
        self.assertTrue((self.target / METADATA_FILE_NAME).exists())
        models = {r["model"] for r in config["records"]}
        self.assertIn("documents.tag", models)
        self.assertIn("paperless_mail.mailaccount", models)
        self.assertNotIn("documents.document", models)
        # secrets are plaintext without a passphrase
        account = next(
            r for r in config["records"] if r["model"] == "paperless_mail.mailaccount"
        )
        self.assertEqual(account["fields"]["password"], "topsecret")

    def test_round_trip_restores_relationships(self) -> None:
        self._export()
        self._wipe_config()
        self.assertEqual(Tag.objects.count(), 0)

        self._import()

        self.assertEqual(Tag.objects.count(), 2)
        child = Tag.objects.get(name="child")
        self.assertEqual(child.parent.name, "parent")
        self.assertEqual(child.color, "#112233")

        view = SavedView.objects.get(name="Tagged child")
        rule = view.filter_rules.get()
        self.assertEqual(rule.value, str(child.pk))

        workflow = Workflow.objects.get(name="Workflow 1")
        self.assertEqual(workflow.triggers.count(), 1)
        self.assertIn(child, workflow.actions.get().assign_tags.all())

        mail_rule = MailRule.objects.get(name="From ACME")
        self.assertIn(child, mail_rule.assign_tags.all())
        self.assertEqual(mail_rule.account.name, "Mailbox")

    def test_import_is_idempotent(self) -> None:
        self._export()
        self._import()
        self._import()
        self.assertEqual(Tag.objects.filter(name="child").count(), 1)
        self.assertEqual(Workflow.objects.filter(name="Workflow 1").count(), 1)
        self.assertEqual(MailRule.objects.filter(name="From ACME").count(), 1)
        self.assertEqual(
            WorkflowAction.objects.filter(assign_title="new title").count(),
            1,
        )

    def test_collision_is_merged(self) -> None:
        self._export()
        # existing object with the same natural key but different attributes
        Tag.objects.filter(name="child").update(color="#000000")
        self._import()
        self.assertEqual(Tag.objects.filter(name="child").count(), 1)
        self.assertEqual(Tag.objects.get(name="child").color, "#112233")

    def test_groups_are_imported_with_permissions(self) -> None:
        """Groups (name + Django permissions, no members) transfer across."""
        group = Group.objects.create(name="cfg_group")
        group.permissions.add(
            Permission.objects.get(
                content_type__app_label="documents",
                content_type__model="tag",
                codename="view_tag",
            ),
        )
        self.action.assign_view_groups.add(group)
        self._export()
        self._wipe_config()
        Group.objects.filter(name="cfg_group").delete()

        self._import()

        imported = Group.objects.get(name="cfg_group")
        self.assertIn("view_tag", {p.codename for p in imported.permissions.all()})
        action = WorkflowAction.objects.get(assign_title="new title")
        self.assertIn(imported, action.assign_view_groups.all())
        self.assertIn(Tag.objects.get(name="child"), action.assign_tags.all())

    def test_unresolvable_user_refs_are_dropped(self) -> None:
        """Users are per-instance; M2M refs to missing users must not crash."""
        other = User.objects.create(username="cfg_other")
        self.action.assign_view_users.add(other)
        self._export()
        self._wipe_config()
        User.objects.filter(username="cfg_other").delete()

        self._import()

        action = WorkflowAction.objects.get(assign_title="new title")
        self.assertEqual(action.assign_view_users.count(), 0)
        self.assertIn(Tag.objects.get(name="child"), action.assign_tags.all())

    def test_dry_run_changes_nothing(self) -> None:
        self._export()
        self._wipe_config()
        self._import(dry_run=True)
        self.assertEqual(Tag.objects.count(), 0)
        self.assertEqual(Workflow.objects.count(), 0)

    def test_passphrase_encrypts_secrets(self) -> None:
        self._export(passphrase="hunter2")
        raw = (self.target / CONFIG_FILE_NAME).read_text()
        self.assertNotIn("topsecret", raw)
        metadata = json.loads((self.target / METADATA_FILE_NAME).read_text())
        self.assertIn(EXPORTER_CRYPTO_SETTINGS_NAME, metadata)

        self._wipe_config()
        self._import(passphrase="hunter2")
        self.assertEqual(MailAccount.objects.get(name="Mailbox").password, "topsecret")

    def test_ui_settings_and_app_config(self) -> None:
        self._export()
        self._wipe_config()
        UiSettings.objects.all().delete()
        self._import()
        settings = UiSettings.objects.get(user=self.user).settings
        self.assertEqual(
            settings["permissions"]["default_view_users"],
            [self.user.pk],
        )
        self.assertEqual(
            ApplicationConfiguration.objects.first().app_title,
            "RKC Test",
        )
