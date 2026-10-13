# RKC: CLI entry point for importing a configuration export into an instance.
# /end RKC edit
from pathlib import Path

from django.core.management.base import BaseCommand

from documents.config_exchange.importer import ConfigImporter


class Command(BaseCommand):
    help = (
        "Import a configuration export (produced by config_exporter) into this "
        "instance. Safe to run against an empty or an already-populated install: "
        "records are matched by name and updated in place."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("source")

        parser.add_argument(
            "--passphrase",
            default=None,
            help="Passphrase used to encrypt sensitive fields in the export.",
        )

        parser.add_argument(
            "--owner",
            default=None,
            help=(
                "Username that should own imported objects. When omitted, owners "
                "are matched by username and fall back to no owner (global)."
            ),
        )

        parser.add_argument(
            "--ui-settings-user",
            dest="ui_settings_user",
            default=None,
            help="Username to apply imported UI settings to (default: match by username).",
        )

        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            default=False,
            action="store_true",
            help="Validate and report what would happen without changing anything.",
        )

        parser.add_argument(
            "--keep-enabled",
            dest="keep_enabled",
            default=False,
            action="store_true",
            help=(
                "Keep imported workflows and mail rules in the enabled state "
                "from the export. By default both are imported disabled so they "
                "cannot run before they have been reviewed."
            ),
        )

        parser.add_argument(
            "--no-preserve-ids",
            dest="preserve_ids",
            default=True,
            action="store_false",
            help=(
                "Let the database assign new primary keys instead of reusing "
                "the ids from the export. By default exported ids are reused "
                "wherever they are free, so tooling that addresses objects by "
                "id (e.g. AI_OCR_TAG_ID) keeps working."
            ),
        )

        parser.add_argument(
            "--no-progress-bar",
            dest="no_progress_bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown.",
        )

    def handle(self, *args, **options) -> None:
        importer = ConfigImporter(
            passphrase=options.get("passphrase"),
            owner=options.get("owner"),
            ui_settings_user=options.get("ui_settings_user"),
            dry_run=options["dry_run"],
            keep_enabled=options["keep_enabled"],
            preserve_ids=options["preserve_ids"],
            no_progress_bar=options["no_progress_bar"],
            stdout=self.stdout,
        )
        importer.run(Path(options["source"]))
