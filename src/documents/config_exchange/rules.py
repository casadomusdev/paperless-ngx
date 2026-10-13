# RKC: Remapping of embedded object ids that are not stored as relations.
# Saved-view filter rule values, workflow custom-field queries and the global
# saved-view ordering all keep ids inside strings/JSON and must be rewritten
# when importing into another instance.
# /end RKC edit
from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from documents.config_exchange.remap import RULE_CUSTOM_FIELD_QUERY
from documents.config_exchange.remap import RULE_MODEL_MULTI
from documents.config_exchange.remap import RULE_MODEL_SINGLE
from documents.config_exchange.remap import RULE_USER_MULTI
from documents.config_exchange.remap import RULE_USER_SINGLE
from documents.models import CustomField
from documents.models import SavedView

if TYPE_CHECKING:
    from django.db.models import Model


def remap_saved_view_rule_value(
    rule_type: int,
    value: str | None,
    maps: dict,
) -> str | None:
    """Rewrite a saved-view filter rule value; ``None`` means drop the rule."""
    if value is None or value == "":
        return value
    if rule_type in RULE_USER_SINGLE or rule_type in RULE_USER_MULTI:
        return None
    if rule_type in RULE_MODEL_SINGLE:
        mapped = _lookup_related(rule_type, _safe_int(value), maps)
        return None if mapped is None else str(mapped)
    if rule_type in RULE_MODEL_MULTI:
        parts = [p for p in value.split(",") if p != ""]
        mapped = [
            str(m)
            for m in (_lookup_related(rule_type, _safe_int(p), maps) for p in parts)
            if m is not None
        ]
        return ",".join(mapped)
    if rule_type == RULE_CUSTOM_FIELD_QUERY:
        return _remap_custom_field_query(value, maps.get(CustomField, {}))
    return value


def _lookup_related(rule_type: int, pk: int | None, maps: dict) -> int | None:
    if pk is None:
        return None
    related = RULE_MODEL_SINGLE.get(rule_type) or RULE_MODEL_MULTI.get(rule_type)
    model_map = maps.get(related) if related else None
    if model_map and pk in model_map:
        return model_map[pk].pk
    return None


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def remap_custom_field_value_map(
    value: dict | None,
    cf_map: dict[int, Model],
) -> dict | None:
    """Remap WorkflowAction.assign_custom_fields_values keys (field id -> value)."""
    if not value:
        return value
    result = {}
    for key, entry in value.items():
        try:
            mapped = cf_map.get(int(key))
        except (TypeError, ValueError):
            mapped = None
        if mapped is not None:
            result[str(mapped.pk)] = entry
    return result


def remap_view_order(value: Any, view_map: dict[int, Model]) -> Any:
    """Remap a list of saved-view ids (ApplicationConfiguration ordering)."""
    if not value:
        return value
    result = []
    for entry in value:
        mapped = view_map.get(_safe_int(str(entry)))
        if mapped is not None:
            result.append(mapped.pk)
    return result


def _remap_custom_field_query(value: str, cf_map: dict[int, Model]) -> str | None:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return value
    remapped = _walk_custom_field_query(parsed, cf_map)
    if remapped is None:
        return None
    return json.dumps(remapped)


def _walk_custom_field_query(node: Any, cf_map: dict[int, Model]) -> Any:
    """Recursively remap custom field ids inside a saved custom field query."""
    if isinstance(node, list):
        if node and isinstance(node[0], int):
            mapped = cf_map.get(node[0])
            if mapped is None:
                return None
            node = [mapped.pk, *node[1:]]
        result = []
        for item in node:
            walked = _walk_custom_field_query(item, cf_map)
            if walked is not None:
                result.append(walked)
        return result
    return node


def hook_workflow_trigger(fields: dict, maps: dict) -> None:
    """Remap embedded custom field ids in a workflow trigger."""
    if fields.get("filter_custom_field_query"):
        fields["filter_custom_field_query"] = _remap_custom_field_query(
            fields["filter_custom_field_query"],
            maps.get(CustomField, {}),
        )


def hook_workflow_action(fields: dict, maps: dict) -> None:
    """Remap embedded custom field ids in a workflow action."""
    if fields.get("assign_custom_fields_values"):
        fields["assign_custom_fields_values"] = remap_custom_field_value_map(
            fields["assign_custom_fields_values"],
            maps.get(CustomField, {}),
        )


def hook_application_config(fields: dict, maps: dict) -> None:
    """Remap saved-view id lists stored on the global application configuration."""
    view_map = maps.get(SavedView, {})
    for key in ("global_sidebar_views_order", "global_dashboard_views_order"):
        if fields.get(key):
            fields[key] = remap_view_order(fields[key], view_map)
