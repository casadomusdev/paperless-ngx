# RKC: Merges a configuration export into a (possibly populated) instance.
# Idempotent: records are matched by natural key (or full field signature) and
# updated in place, so it is safe to run against a fresh or an existing install.
# /end RKC edit
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile
from zipfile import is_zipfile

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.core.management.color import color_style
from django.db import transaction

from documents.config_exchange.exporter import CONFIG_FILE_NAME
from documents.config_exchange.exporter import METADATA_FILE_NAME
from documents.config_exchange.registry import CHILDREN
from documents.config_exchange.registry import CONFIG_MODELS
from documents.config_exchange.registry import GROUP
from documents.config_exchange.registry import SIGNATURE
from documents.config_exchange.registry import SINGLETON
from documents.config_exchange.registry import UI_SETTINGS
from documents.config_exchange.registry import ConfigModel
from documents.config_exchange.strategies import MergeStrategyMixin
from documents.management.commands.mixins import CryptMixin
from documents.settings import EXPORTER_CRYPTO_SETTINGS_NAME
from paperless import version


class ConfigImporter(MergeStrategyMixin, CryptMixin):
    """Applies a configuration export to the current instance."""

    def __init__(
        self,
        *,
        passphrase: str | None = None,
        owner: str | None = None,
        ui_settings_user: str | None = None,
        dry_run: bool = False,
        keep_enabled: bool = False,
        preserve_ids: bool = True,
        no_progress_bar: bool = False,
        stdout=None,
    ) -> None:
        self.passphrase = passphrase
        self.owner_username = owner
        self.ui_settings_user = ui_settings_user
        self.dry_run = dry_run
        self.keep_enabled = keep_enabled
        self.preserve_ids = preserve_ids
        self.no_progress_bar = no_progress_bar
        self.stdout = stdout

        self.records: list[dict] = []
        self.references: dict[str, dict] = {"auth.user": {}}
        self.assets: dict[str, str] = {}
        self.maps: dict = {}
        self.target_users: dict[str, User] = {}
        self.target_permissions: dict[tuple[str, str, str], int] = {}
        self.owner_override_id: int | None = None
        self._signature_index: dict[str, dict[str, object]] = {}
        self._cleared_rule_views: set = set()
        self._source_version: str | None = None

    def _log(self, message: str) -> None:
        if self.stdout is not None:
            self.stdout.write(message)

    def _warn(self, message: str) -> None:
        if self.stdout is not None:
            self.stdout.write(color_style().WARNING(message))

    def run(self, source: Path) -> None:
        given = Path(source)
        resolved = given.expanduser().resolve()
        if not resolved.exists():
            raise CommandError(
                f"That path doesn't exist: {resolved} "
                f"(argument '{given}', current directory '{Path.cwd()}')",
            )
        source = resolved

        temp_dir = None
        try:
            if is_zipfile(source):
                temp_dir = tempfile.TemporaryDirectory()
                with ZipFile(source) as zf:
                    zf.extractall(temp_dir.name)
                source = Path(temp_dir.name)

            self._load_bundle(source)
            self._load_metadata(source)
            self._decrypt_secrets()
            self._build_resolvers()

            with transaction.atomic():
                self._import_all(source)
                if self.dry_run:
                    transaction.set_rollback(True)
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

        if self.dry_run:
            self._log("Dry run complete. No changes were made.")
        else:
            self._log("Configuration import complete.")

    def _load_bundle(self, source: Path) -> None:
        config_path = source / CONFIG_FILE_NAME
        if not config_path.exists():
            raise CommandError(
                "That directory doesn't appear to contain a config.json file.",
            )
        with config_path.open() as infile:
            data = json.load(infile)
        self.records = data.get("records", [])
        self.references = data.get("references", self.references)
        self.assets = data.get("assets", {})

    def _load_metadata(self, source: Path) -> None:
        metadata_path = source / METADATA_FILE_NAME
        if not metadata_path.exists():
            return
        with metadata_path.open() as infile:
            data = json.load(infile)
        self._source_version = data.get("version")
        if EXPORTER_CRYPTO_SETTINGS_NAME in data:
            if not self.passphrase:
                raise CommandError(
                    "No passphrase was given, but this export contains "
                    "encrypted fields",
                )
            self.load_crypt_params(data)
        if (
            self._source_version
            and self._source_version != version.__full_version_str__
        ):
            self._warn(
                f"Version mismatch: currently {version.__full_version_str__}, "
                f"export created with {self._source_version}. Continuing.",
            )

    def _decrypt_secrets(self) -> None:
        if not self.passphrase:
            return
        self.setup_crypto(passphrase=self.passphrase, salt=self.salt)
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
                        record["fields"][field_name] = self.decrypt_string(value=value)

    def _build_resolvers(self) -> None:
        self.target_users = {u.username: u for u in User.objects.all()}
        # Permissions are per-instance rows; identify them by their stable
        # (app_label, model, codename) triple so group permissions can be
        # remapped across instances.
        self.target_permissions = {
            (app_label, model, codename): pk
            for pk, app_label, model, codename in Permission.objects.values_list(
                "pk",
                "content_type__app_label",
                "content_type__model",
                "codename",
            )
        }
        if self.owner_username:
            user = self.target_users.get(self.owner_username)
            if user is None:
                raise CommandError(
                    f"Owner user '{self.owner_username}' does not exist on this instance",
                )
            self.owner_override_id = user.pk

    def resolve_user(self, pk) -> int | None:
        if pk is None:
            return None
        if self.owner_override_id is not None:
            return self.owner_override_id
        username = self.references.get("auth.user", {}).get(str(pk))
        user = self.target_users.get(username) if username else None
        return user.pk if user is not None else None

    def _records_for(self, cm: ConfigModel) -> list[dict]:
        label = cm.model._meta.label_lower
        return [r for r in self.records if r["model"] == label]

    def _import_all(self, source: Path) -> None:
        for cm in CONFIG_MODELS:
            if cm.strategy == CHILDREN:
                self._import_children(cm)
            elif cm.strategy == SIGNATURE:
                self._import_signature(cm)
            elif cm.strategy == UI_SETTINGS:
                self._import_ui_settings(cm)
            elif cm.strategy == SINGLETON:
                self._import_singleton(cm, source)
            elif cm.strategy == GROUP:
                self._import_groups(cm)
            else:
                self._import_upsert(cm)
            self._log(f"Imported {cm.key}")
        self._reset_sequences()
