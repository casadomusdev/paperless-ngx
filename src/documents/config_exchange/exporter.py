# RKC: Serializes all paperless configuration into a portable bundle.
# /end RKC edit
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.core import serializers
from django.core.management.base import CommandError
from django.utils import timezone

from documents.config_exchange.registry import CONFIG_MODELS
from documents.config_exchange.registry import CONFIG_MODELS_BY_LABEL
from documents.config_exchange.remap import RULE_USER_MULTI
from documents.config_exchange.remap import RULE_USER_SINGLE
from documents.config_exchange.remap import iter_user_group_refs
from documents.management.commands.mixins import CryptMixin
from documents.models import SavedViewFilterRule
from paperless import version
from paperless.models import ApplicationConfiguration

CONFIG_FILE_NAME = "config.json"
METADATA_FILE_NAME = "metadata.json"
ASSETS_DIR_NAME = "assets"


class ConfigExporter(CryptMixin):
    """Writes a configuration-only export (no documents) to a target folder."""

    def __init__(
        self,
        *,
        passphrase: str | None = None,
        zip_export: bool = False,
        zip_name: str | None = None,
        no_progress_bar: bool = False,
        stdout=None,
    ) -> None:
        self.passphrase = passphrase
        self.zip_export = zip_export
        self.zip_name = zip_name or f"config-export-{timezone.localdate().isoformat()}"
        self.no_progress_bar = no_progress_bar
        self.stdout = stdout
        self.records: list[dict] = []
        self.references: dict[str, dict] = {"auth.user": {}, "auth.group": {}}
        self.assets: dict[str, str] = {}

    def _log(self, message: str) -> None:
        if self.stdout is not None:
            self.stdout.write(message)

    def run(self, target: Path) -> None:
        given = Path(target)
        resolved = given.expanduser().resolve()
        if not resolved.exists():
            raise CommandError(
                f"That path doesn't exist: {resolved} "
                f"(argument '{given}', current directory '{Path.cwd()}')",
            )
        if not resolved.is_dir():
            raise CommandError(f"That path isn't a directory: {resolved}")
        target = resolved

        temp_dir = None
        original_target = target
        if self.zip_export:
            settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
            temp_dir = tempfile.TemporaryDirectory(
                dir=settings.SCRATCH_DIR,
                prefix="paperless-config-export",
            )
            target = Path(temp_dir.name).resolve()

        try:
            self._collect_records()
            self._collect_references()
            self._encrypt_secrets()
            self._export_assets(target)
            self._write_bundle(target)
            if self.zip_export and temp_dir is not None:
                shutil.make_archive(
                    str(original_target / self.zip_name),
                    format="zip",
                    root_dir=temp_dir.name,
                )
                self._log(f"Wrote {original_target / (self.zip_name + '.zip')}")
            else:
                self._log(f"Wrote configuration export to {target}")
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

    def _collect_records(self) -> None:
        for cm in CONFIG_MODELS:
            serialized = json.loads(
                serializers.serialize("json", cm.model.objects.all()),
            )
            self.records.extend(serialized)

    def _collect_references(self) -> None:
        user_pks: set[int] = set()
        group_pks: set[int] = set()
        for record in self.records:
            cm = CONFIG_MODELS_BY_LABEL[record["model"]]
            for related, pk in iter_user_group_refs(cm.model, record["fields"]):
                if related is User:
                    user_pks.add(pk)
                else:
                    group_pks.add(pk)
        user_pks.update(self._filter_rule_user_pks())
        self.references["auth.user"] = self._user_names(user_pks)
        self.references["auth.group"] = self._group_names(group_pks)

    def _filter_rule_user_pks(self) -> set[int]:
        pks: set[int] = set()
        for rule in SavedViewFilterRule.objects.all():
            if not rule.value:
                continue
            if rule.rule_type in RULE_USER_SINGLE:
                if rule.value.isdigit():
                    pks.add(int(rule.value))
            elif rule.rule_type in RULE_USER_MULTI:
                pks.update(
                    int(part) for part in rule.value.split(",") if part.isdigit()
                )
        return pks

    @staticmethod
    def _user_names(pks: set[int]) -> dict[str, str]:
        return {
            str(pk): username
            for pk, username in User.objects.filter(pk__in=pks).values_list(
                "pk",
                "username",
            )
        }

    @staticmethod
    def _group_names(pks: set[int]) -> dict[str, str]:
        return {
            str(pk): name
            for pk, name in Group.objects.filter(pk__in=pks).values_list("pk", "name")
        }

    def _encrypt_secrets(self) -> None:
        if not self.passphrase:
            return
        self.setup_crypto(passphrase=self.passphrase)
        for cm in CONFIG_MODELS:
            if not cm.secret_fields:
                continue
            label = cm.model._meta.label_lower
            for record in self.records:
                if record["model"] != label:
                    continue
                for field_name in cm.secret_fields:
                    value = record["fields"].get(field_name)
                    if value:
                        record["fields"][field_name] = self.encrypt_string(value=value)

    def _export_assets(self, target: Path) -> None:
        config = ApplicationConfiguration.objects.first()
        if not config or not config.app_logo:
            return
        source = Path(config.app_logo.path)
        if not source.exists():
            return
        assets_dir = target / ASSETS_DIR_NAME
        assets_dir.mkdir(parents=True, exist_ok=True)
        dest_name = f"app_logo{source.suffix}"
        shutil.copy2(source, assets_dir / dest_name)
        self.assets["app_logo"] = dest_name

    def _write_bundle(self, target: Path) -> None:
        config_data = {
            "version": version.__full_version_str__,
            "exported_at": timezone.now().isoformat(),
            "records": self.records,
            "references": self.references,
            "assets": self.assets,
        }
        (target / CONFIG_FILE_NAME).write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        metadata: dict = {"version": version.__full_version_str__}
        if self.passphrase:
            metadata.update(self.get_crypt_params())
        (target / METADATA_FILE_NAME).write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
