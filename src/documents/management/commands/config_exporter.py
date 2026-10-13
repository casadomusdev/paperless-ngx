# RKC: CLI entry point for exporting all paperless configuration between instances.
# /end RKC edit
from pathlib import Path

from django.core.management.base import BaseCommand

from documents.config_exchange.exporter import ConfigExporter


class Command(BaseCommand):
    help = (
        "Export all paperless configuration (tags, document types, storage paths, "
        "correspondents, custom fields, saved views, workflows, mail accounts and "
        "rules, UI settings and application configuration) to a folder or zip file "
        "for import into another instance. Documents are not included."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("target")

        parser.add_argument(
            "-z",
            "--zip",
            default=False,
            action="store_true",
            help="Write the export as a zip file in the target directory.",
        )

        parser.add_argument(
            "-zn",
            "--zip-name",
            default=None,
            help="Name of the zip file (without extension).",
        )

        parser.add_argument(
            "--passphrase",
            default=None,
            help="Encrypt sensitive fields (mail passwords/tokens) with this passphrase.",
        )

        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown.",
        )

    def handle(self, *args, **options) -> None:
        exporter = ConfigExporter(
            passphrase=options.get("passphrase"),
            zip_export=options["zip"],
            zip_name=options.get("zip_name"),
            no_progress_bar=options["no_progress_bar"],
            stdout=self.stdout,
        )
        exporter.run(Path(options["target"]))
