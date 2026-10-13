# RKC: PK remapping helpers for configuration export / import.
# Cross-instance imports must translate every foreign key, many-to-many entry
# and embedded id (saved-view filter rules, custom field queries) from the
# source instance to the target instance.
# /end RKC edit
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

from django.contrib.auth.models import User

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import Model

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag

MISSING = object()

# Saved-view filter rule types carrying object ids (see models.SavedViewFilterRule)
RULE_MODEL_SINGLE: dict[int, type[Model]] = {
    3: Correspondent,
    4: DocumentType,
    25: StoragePath,
}
RULE_MODEL_MULTI: dict[int, type[Model]] = {
    6: Tag,
    17: Tag,
    22: Tag,
    26: Correspondent,
    27: Correspondent,
    28: DocumentType,
    29: DocumentType,
    30: StoragePath,
    31: StoragePath,
    38: CustomField,
    39: CustomField,
    40: CustomField,
}
# Rule types that reference user ids. Users are per-instance and never imported,
# so these rules cannot be carried across and are dropped.
RULE_USER_SINGLE: frozenset[int] = frozenset({32})
RULE_USER_MULTI: frozenset[int] = frozenset({33, 35, 37})
RULE_CUSTOM_FIELD_QUERY = 42


@dataclass
class Remapped:
    scalars: dict
    m2m: dict[str, list]
    deferred_self: dict[str, Any]
    missing: list[str]
    missing_required: list[str]


def relation_fields(model: type[Model]) -> Iterable:
    """Yield forward relation fields (FKs and many-to-many), not reverse ones."""
    for f in model._meta.get_fields():
        if not f.is_relation or f.auto_created:
            continue
        # ``concrete`` is False for ManyToManyField, so check it explicitly
        if f.many_to_many or f.concrete:
            yield f


def remap_fields(
    model: type[Model],
    fields: dict,
    maps: dict[type[Model], dict[int, Model]],
    resolve_user,
) -> Remapped:
    """Translate all relation ids in ``fields`` using previously built maps."""
    scalars = dict(fields)
    m2m: dict[str, list] = {}
    deferred: dict[str, Any] = {}
    missing: list[str] = []
    missing_required: list[str] = []

    for f in relation_fields(model):
        name = f.name
        if name not in fields:
            continue
        related = f.related_model
        if f.many_to_many:
            new_values = []
            for value in fields.get(name) or []:
                result = _remap_single(related, value, maps, resolve_user)
                # Users are per-instance and never imported, so an unresolved
                # user entry resolves to None and must be dropped rather than
                # inserted as a NULL join row.
                if result is MISSING or result is None:
                    missing.append(f"{name}[{value}]")
                else:
                    new_values.append(result)
            m2m[name] = new_values
            scalars.pop(name, None)
        elif related is model:
            # Self referential FK (e.g. Tag.tn_parent) is resolved after the
            # whole model has been imported.
            scalars.pop(name, None)
            deferred[f.attname] = fields.get(name)
            scalars[f.attname] = None
        else:
            result = _remap_single(related, fields.get(name), maps, resolve_user)
            # FK values are assigned by attname (owner -> owner_id) so they can
            # be passed straight to the model constructor.
            scalars.pop(name, None)
            if result is MISSING:
                missing.append(f"{name}={fields.get(name)}")
                scalars[f.attname] = None
                if not f.null:
                    missing_required.append(name)
            else:
                scalars[f.attname] = result

    return Remapped(scalars, m2m, deferred, missing, missing_required)


def resolve_deferred(
    model: type[Model],
    deferred: dict[str, Any],
    maps: dict[type[Model], dict[int, Model]],
    resolve_user,
) -> dict[str, Any]:
    resolved = {}
    for name, value in deferred.items():
        if value is None:
            continue
        result = _remap_single(model, value, maps, resolve_user)
        if result is not MISSING:
            resolved[name] = result
    return resolved


def _remap_single(related, value, maps, resolve_user):
    """Resolve a single reference to a target pk, or ``MISSING``."""
    if value is None:
        return None
    if related is User:
        # Users are per-instance; only a same-named existing user can be used.
        return resolve_user(value)
    model_map = maps.get(related)
    if model_map is not None and value in model_map:
        return model_map[value].pk
    return MISSING


def iter_user_refs(model: type[Model], fields: dict) -> Iterable[int]:
    """Yield user pks referenced by a serialized record (for name mapping)."""
    for f in relation_fields(model):
        if f.related_model is not User or f.name not in fields:
            continue
        value = fields.get(f.name)
        if value is None:
            continue
        if f.many_to_many:
            yield from value
        else:
            yield value
