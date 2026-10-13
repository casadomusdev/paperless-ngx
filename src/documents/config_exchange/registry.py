# RKC: Declarative registry of configuration models exchanged between instances.
# This is the single source of truth for what counts as "configuration", the
# order in which records are imported (dependency ordered), how records are
# matched on the target instance (natural keys) and which fields are secret.
# /end RKC edit
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import Model

from django.contrib.auth.models import Group

from documents.config_exchange.rules import hook_application_config
from documents.config_exchange.rules import hook_workflow_action
from documents.config_exchange.rules import hook_workflow_trigger
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
from documents.models import WorkflowActionEmail
from documents.models import WorkflowActionWebhook
from documents.models import WorkflowTrigger
from paperless.models import ApplicationConfiguration
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule

# Import strategies
UPSERT = "upsert"  # match by natural key, update in place or create
SIGNATURE = "signature"  # match by full field signature, reuse identical row
CHILDREN = "children"  # owned by a parent, rules are replaced on import
UI_SETTINGS = "ui_settings"  # handled specially (keyed by username)
SINGLETON = "singleton"  # single global row (ApplicationConfiguration)
GROUP = "group"  # name + Django permissions, but not members (handled specially)


@dataclass(frozen=True)
class ConfigModel:
    """A single configuration model participating in the exchange."""

    model: type[Model]
    key: str
    natural_key: tuple[str, ...] | None = None
    owner_field: str | None = None
    secret_fields: tuple[str, ...] = ()
    strategy: str = UPSERT
    parent_field: str | None = None
    # Boolean field forced to False on import so that imported automations do
    # not start running before they have been reviewed (opt out with
    # --keep-enabled).
    disable_field: str | None = None
    remap_hook: Callable | None = dataclass_field(default=None, compare=False)


# Order matters: dependencies must be imported before their dependents.
CONFIG_MODELS: list[ConfigModel] = [
    # Groups are imported first: workflow actions and UI settings reference them.
    ConfigModel(Group, "groups", ("name",), strategy=GROUP),
    ConfigModel(Correspondent, "correspondents", ("name",), owner_field="owner"),
    ConfigModel(Tag, "tags", ("name",), owner_field="owner"),
    ConfigModel(DocumentType, "document_types", ("name",), owner_field="owner"),
    ConfigModel(StoragePath, "storage_paths", ("name",), owner_field="owner"),
    ConfigModel(CustomField, "custom_fields", ("name",)),
    ConfigModel(
        MailAccount,
        "mail_accounts",
        ("name",),
        owner_field="owner",
        secret_fields=("password", "refresh_token", "smtp_password"),
    ),
    ConfigModel(
        MailRule,
        "mail_rules",
        ("name",),
        owner_field="owner",
        disable_field="enabled",
    ),
    ConfigModel(SavedView, "saved_views", ("name",), owner_field="owner"),
    ConfigModel(
        SavedViewFilterRule,
        "saved_view_filter_rules",
        strategy=CHILDREN,
        parent_field="saved_view",
    ),
    ConfigModel(
        WorkflowTrigger,
        "workflow_triggers",
        strategy=SIGNATURE,
        remap_hook=hook_workflow_trigger,
    ),
    ConfigModel(WorkflowActionEmail, "workflow_email_actions", strategy=SIGNATURE),
    ConfigModel(WorkflowActionWebhook, "workflow_webhook_actions", strategy=SIGNATURE),
    ConfigModel(
        WorkflowAction,
        "workflow_actions",
        strategy=SIGNATURE,
        remap_hook=hook_workflow_action,
    ),
    ConfigModel(Workflow, "workflows", ("name",), disable_field="enabled"),
    ConfigModel(UiSettings, "ui_settings", strategy=UI_SETTINGS),
    ConfigModel(
        ApplicationConfiguration,
        "app_configs",
        strategy=SINGLETON,
        remap_hook=hook_application_config,
    ),
]

CONFIG_MODELS_BY_KEY: dict[str, ConfigModel] = {cm.key: cm for cm in CONFIG_MODELS}
CONFIG_MODELS_BY_MODEL: dict[type[Model], ConfigModel] = {
    cm.model: cm for cm in CONFIG_MODELS
}
CONFIG_MODELS_BY_LABEL: dict[str, ConfigModel] = {
    cm.model._meta.label_lower: cm for cm in CONFIG_MODELS
}

# Exporter keys are used verbatim in config.json; keep in sync with tests.
MANIFEST_RECORDS_KEY = "records"
MANIFEST_REFERENCES_KEY = "references"
