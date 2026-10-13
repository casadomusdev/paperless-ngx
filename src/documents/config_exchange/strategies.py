# RKC: Import strategies used by ConfigImporter (merge engine).
# Kept separate from the loader/orchestrator so each module stays small.
# /end RKC edit
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import Group
from django.core import serializers

from documents.config_exchange.exporter import ASSETS_DIR_NAME
from documents.config_exchange.remap import relation_fields
from documents.config_exchange.remap import remap_fields
from documents.config_exchange.remap import resolve_deferred
from documents.config_exchange.rules import remap_saved_view_rule_value
from documents.models import SavedViewFilterRule
from documents.models import UiSettings

if TYPE_CHECKING:
    from documents.config_exchange.registry import ConfigModel


class MergeStrategyMixin:
    """Merge strategies mixed into :class:`ConfigImporter`."""

    def _import_upsert(self, cm: ConfigModel) -> None:
        label = cm.model._meta.label_lower
        model_map: dict = {}
        deferred: list[tuple[dict, object]] = []
        for record in self._records_for(cm):
            remapped = remap_fields(
                cm.model,
                record["fields"],
                self.maps,
                self.resolve_user,
            )
            if remapped.missing:
                self._warn(f"{label}: unresolved references {remapped.missing}")
            if remapped.missing_required:
                self._warn(
                    f"{label}: skipping record with unresolved required "
                    f"references {remapped.missing_required}",
                )
                continue
            if cm.remap_hook is not None:
                cm.remap_hook(remapped.scalars, self.maps)
            if cm.disable_field and not self.keep_enabled:
                # Imported automations start disabled so they cannot fire
                # before an admin has reviewed them.
                remapped.scalars[cm.disable_field] = False
            scalars = clean_scalars(cm.model, remapped.scalars)
            instance = self._match_or_create(cm, scalars)
            apply_m2m(instance, remapped.m2m)
            model_map[record["pk"]] = instance
            if remapped.deferred_self:
                deferred.append((remapped.deferred_self, instance))
        self.maps[cm.model] = model_map
        if cm.disable_field and not self.keep_enabled:
            self._log(f"Imported {cm.key} disabled - review before enabling")
        for deferred_fields, instance in deferred:
            resolved = resolve_deferred(
                cm.model,
                deferred_fields,
                self.maps,
                self.resolve_user,
            )
            if resolved:
                for attname, value in resolved.items():
                    setattr(instance, attname, value)
                instance.save()

    def _match_or_create(self, cm: ConfigModel, scalars: dict):
        if cm.natural_key:
            lookup = {key: scalars.get(key) for key in cm.natural_key}
            if all(value is not None for value in lookup.values()):
                existing = cm.model.objects.filter(**lookup).first()
                if existing is not None:
                    return self._update(existing, scalars)
        instance = cm.model(**scalars)
        instance.save()
        return instance

    @staticmethod
    def _update(instance, scalars: dict):
        for name, value in scalars.items():
            setattr(instance, name, value)
        instance.save()
        return instance

    def _import_signature(self, cm: ConfigModel) -> None:
        label = cm.model._meta.label_lower
        index = self._signature_index.setdefault(label, {})
        if not index:
            for obj in cm.model.objects.all():
                data = json.loads(serializers.serialize("json", [obj]))[0]["fields"]
                index[field_signature(data)] = obj
        model_map: dict = {}
        for record in self._records_for(cm):
            remapped = remap_fields(
                cm.model,
                record["fields"],
                self.maps,
                self.resolve_user,
            )
            if remapped.missing_required:
                self._warn(
                    f"{label}: skipping record with unresolved required "
                    f"references {remapped.missing_required}",
                )
                continue
            if cm.remap_hook is not None:
                cm.remap_hook(remapped.scalars, self.maps)
            signature = field_signature(
                signature_fields(cm.model, remapped.scalars, remapped.m2m),
            )
            existing = index.get(signature)
            if existing is not None:
                model_map[record["pk"]] = existing
                continue
            scalars = clean_scalars(cm.model, remapped.scalars)
            instance = cm.model(**scalars)
            instance.save()
            apply_m2m(instance, remapped.m2m)
            index[signature] = instance
            model_map[record["pk"]] = instance
        self.maps[cm.model] = model_map

    def _import_children(self, cm: ConfigModel) -> None:
        parent_model = cm.model._meta.get_field(cm.parent_field).related_model
        parent_map = self.maps.get(parent_model, {})
        grouped: dict = defaultdict(list)
        for record in self._records_for(cm):
            old_parent = record["fields"].get(cm.parent_field)
            if old_parent not in parent_map:
                self._warn(f"{cm.key}: parent {old_parent} not imported, skipping rule")
                continue
            grouped[old_parent].append(record)

        for old_parent, records in grouped.items():
            parent = parent_map[old_parent]
            if parent.pk not in self._cleared_rule_views:
                SavedViewFilterRule.objects.filter(saved_view=parent).delete()
                self._cleared_rule_views.add(parent.pk)
            for record in records:
                fields = record["fields"]
                value = remap_saved_view_rule_value(
                    fields.get("rule_type"),
                    fields.get("value"),
                    self.maps,
                )
                if value is None:
                    self._warn(
                        f"{cm.key}: dropped rule {fields.get('rule_type')} "
                        "referencing a per-instance user",
                    )
                    continue
                SavedViewFilterRule.objects.create(
                    saved_view=parent,
                    rule_type=fields["rule_type"],
                    value=value,
                )
        self.maps[cm.model] = {}

    def _import_groups(self, cm: ConfigModel) -> None:
        """Import groups by name with their Django permissions (no members)."""
        permission_refs = self.references.get("auth.permission", {})
        model_map: dict = {}
        for record in self._records_for(cm):
            fields = record["fields"]
            group, _ = Group.objects.get_or_create(name=fields["name"])
            permission_pks = []
            for pk in fields.get("permissions") or []:
                key = permission_refs.get(str(pk))
                target_pk = self.target_permissions.get(tuple(key)) if key else None
                if target_pk is None:
                    self._warn(
                        f"{cm.key}: permission '{key}' is not on this instance, "
                        "skipping",
                    )
                    continue
                permission_pks.append(target_pk)
            group.permissions.set(permission_pks)
            model_map[record["pk"]] = group
        self.maps[cm.model] = model_map

    def _import_ui_settings(self, cm: ConfigModel) -> None:
        user_refs = self.references.get("auth.user", {})
        for record in self._records_for(cm):
            fields = record["fields"]
            source_username = user_refs.get(str(fields.get("user")))
            target_username = self.ui_settings_user or source_username
            user = self.target_users.get(target_username) if target_username else None
            if user is None:
                self._warn(f"{cm.key}: no target user '{target_username}', skipping")
                continue
            settings_data = self._remap_permissions(fields.get("settings") or {})
            UiSettings.objects.update_or_create(
                user=user,
                defaults={"settings": settings_data},
            )
        self.maps[cm.model] = {}

    def _remap_permissions(self, settings_data: dict) -> dict:
        if not isinstance(settings_data, dict):
            return settings_data
        permissions = settings_data.get("permissions")
        if not isinstance(permissions, dict):
            return settings_data
        updated = dict(permissions)
        owner = permissions.get("default_owner")
        if owner is not None:
            updated["default_owner"] = self.resolve_user(owner)
        for key in ("default_view_users", "default_change_users"):
            if isinstance(permissions.get(key), list):
                updated[key] = [
                    mapped
                    for mapped in (self.resolve_user(p) for p in permissions[key])
                    if mapped is not None
                ]
        group_map = self.maps.get(Group, {})
        for key in ("default_view_groups", "default_change_groups"):
            if isinstance(permissions.get(key), list):
                updated[key] = [
                    group_map[p].pk for p in permissions[key] if p in group_map
                ]
        settings_data["permissions"] = updated
        return settings_data

    def _import_singleton(self, cm: ConfigModel, source: Path) -> None:
        self.maps[cm.model] = {}
        for record in self._records_for(cm):
            remapped = remap_fields(
                cm.model,
                record["fields"],
                self.maps,
                self.resolve_user,
            )
            if cm.remap_hook is not None:
                cm.remap_hook(remapped.scalars, self.maps)
            scalars = clean_scalars(cm.model, remapped.scalars)
            instance = cm.model.objects.first() or cm.model()
            for name, value in scalars.items():
                setattr(instance, name, value)
            instance.save()
            self._copy_logo(source, scalars.get("app_logo"))

    def _copy_logo(self, source: Path, logo_path: str | None) -> None:
        asset_name = self.assets.get("app_logo")
        if not asset_name or self.dry_run:
            return
        asset = source / ASSETS_DIR_NAME / asset_name
        if not asset.exists():
            return
        relative = logo_path or f"logo/{asset_name}"
        destination = Path(settings.MEDIA_ROOT) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)


def clean_scalars(model, scalars: dict) -> dict:
    """Keep only settable concrete, non-primary-key fields (name or attname)."""
    allowed: set[str] = set()
    for field in model._meta.concrete_fields:
        allowed.add(field.name)
        allowed.add(field.attname)
    allowed.discard(model._meta.pk.name)
    allowed.discard(model._meta.pk.attname)
    return {key: value for key, value in scalars.items() if key in allowed}


def apply_m2m(instance, m2m: dict[str, list]) -> None:
    for name, values in m2m.items():
        # A NULL pk can never form a valid join row (the through column is
        # NOT NULL), so defensively drop any that slipped through remapping —
        # e.g. an unresolvable user/group reference.
        getattr(instance, name).set([value for value in values if value is not None])


def signature_fields(model, scalars: dict, m2m: dict) -> dict:
    """
    Build a field-name keyed dict for signature comparison.

    Records use foreign key attnames (owner_id) while Django's serializer emits
    field names (owner); normalise so both sides produce identical signatures.
    """
    merged = dict(scalars)
    for field in relation_fields(model):
        if not field.many_to_many and field.attname in merged:
            merged[field.name] = merged.pop(field.attname)
    merged.update(m2m)
    return merged


def field_signature(fields: dict) -> str:
    normalized = {
        key: sorted(value) if isinstance(value, list) else value
        for key, value in fields.items()
    }
    return json.dumps(normalized, sort_keys=True, default=str)
