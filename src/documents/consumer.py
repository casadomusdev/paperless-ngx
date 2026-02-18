import datetime
import hashlib
import logging
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import magic
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from filelock import FileLock
from rest_framework.reverse import reverse

from documents.classifier import load_classifier
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.file_handling import create_source_path_directory
from documents.file_handling import generate_unique_filename
from documents.loggers import LoggingMixin
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import StoragePath
from documents.models import Tag
from documents.models import WorkflowTrigger
from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import get_parser_class_for_mime_type
from documents.parsers import parse_date
from documents.permissions import set_permissions_for_object
from documents.plugins.base import AlwaysRunPluginMixin
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import NoCleanupPluginMixin
from documents.plugins.base import NoSetupPluginMixin
from documents.plugins.base import StopConsumeTaskError
from documents.plugins.helpers import ProgressManager
from documents.plugins.helpers import ProgressStatusOptions
from documents.signals import document_consumption_finished
from documents.signals import document_consumption_started
from documents.signals.handlers import run_workflows
from documents.templating.workflows import parse_w_workflow_placeholders
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats
from documents.utils import run_subprocess
from paperless_mail.parsers import MailDocumentParser


# RKC: Helper function to attach email metadata as custom fields
def _attach_mail_metadata_custom_fields(
    document,
    mail_uid: str | None = None,
    mail_from: str | None = None,
    mail_sender: str | None = None,
    mail_subject: str | None = None,
    mail_date: datetime.date | None = None,
):
    """
    Attaches email metadata to the document as custom fields.
    Creates custom field definitions if they don't exist.
    
    Args:
        document: The Document instance to attach fields to
        mail_uid: The IMAP UID from the source email
        mail_from: The sender's email address
        mail_sender: The sender's display name
        mail_subject: The email subject line
        mail_date: The email received date
    """
    logger = logging.getLogger("paperless.consumer")
    
    # Define all metadata fields with their settings keys and data types
    metadata_fields = [
        {
            'value': mail_uid,
            'setting_key': 'PAPERLESS_MAIL_CORRELATION_FIELD',
            'data_type': CustomField.FieldDataType.STRING,
            'value_field': 'value_text',
            'label': 'Mail UID',
        },
        {
            'value': mail_from,
            'setting_key': 'PAPERLESS_MAIL_FROM_FIELD',
            'data_type': CustomField.FieldDataType.STRING,
            'value_field': 'value_text',
            'label': 'Mail From',
        },
        {
            'value': mail_sender,
            'setting_key': 'PAPERLESS_MAIL_SENDER_FIELD',
            'data_type': CustomField.FieldDataType.STRING,
            'value_field': 'value_text',
            'label': 'Mail Sender',
        },
        {
            'value': mail_subject,
            'setting_key': 'PAPERLESS_MAIL_SUBJECT_FIELD',
            'data_type': CustomField.FieldDataType.STRING,
            'value_field': 'value_text',
            'label': 'Mail Subject',
        },
        {
            'value': mail_date,
            'setting_key': 'PAPERLESS_MAIL_DATE_FIELD',
            'data_type': CustomField.FieldDataType.DATE,
            'value_field': 'value_date',
            'label': 'Mail Date',
        },
    ]
    
    # Process each metadata field
    for field_config in metadata_fields:
        # Skip if no value provided
        if field_config['value'] is None:
            continue
        
        try:
            # Get or create the custom field definition
            field_name = getattr(settings, field_config['setting_key'])
            field, created = CustomField.objects.get_or_create(
                name=field_name,
                defaults={
                    'data_type': field_config['data_type'],
                }
            )
            
            if created:
                logger.info(f"Created mail metadata custom field: {field_name}")
            
            # Set the custom field value for this document
            CustomFieldInstance.objects.update_or_create(
                document=document,
                field=field,
                defaults={
                    field_config['value_field']: field_config['value'],
                }
            )
            
            logger.debug(
                f"Attached {field_config['label']} to document {document.pk}"
            )
            
        except Exception as e:
            logger.warning(
                f"Failed to attach {field_config['label']} custom field: {e}"
            )
            # Don't raise - this is a non-critical enhancement
# /end RKC edit


class WorkflowTriggerPlugin(
    NoCleanupPluginMixin,
    NoSetupPluginMixin,
    AlwaysRunPluginMixin,
    ConsumeTaskPlugin,
):
    NAME: str = "WorkflowTriggerPlugin"

    def run(self) -> str | None:
        """
        Get overrides from matching workflows
        """
        overrides, msg = run_workflows(
            trigger_type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            document=self.input_doc,
            logging_group=None,
            overrides=DocumentMetadataOverrides(),
        )
        if overrides:
            self.metadata.update(overrides)
        return msg


class ConsumerError(Exception):
    pass


class ConsumerStatusShortMessage(str, Enum):
    DOCUMENT_ALREADY_EXISTS = "document_already_exists"
    DOCUMENT_ALREADY_EXISTS_IN_TRASH = "document_already_exists_in_trash"
    ASN_ALREADY_EXISTS = "asn_already_exists"
    ASN_ALREADY_EXISTS_IN_TRASH = "asn_already_exists_in_trash"
    ASN_RANGE = "asn_value_out_of_range"
    FILE_NOT_FOUND = "file_not_found"
    PRE_CONSUME_SCRIPT_NOT_FOUND = "pre_consume_script_not_found"
    PRE_CONSUME_SCRIPT_ERROR = "pre_consume_script_error"
    POST_CONSUME_SCRIPT_NOT_FOUND = "post_consume_script_not_found"
    POST_CONSUME_SCRIPT_ERROR = "post_consume_script_error"
    NEW_FILE = "new_file"
    UNSUPPORTED_TYPE = "unsupported_type"
    PARSING_DOCUMENT = "parsing_document"
    GENERATING_THUMBNAIL = "generating_thumbnail"
    PARSE_DATE = "parse_date"
    SAVE_DOCUMENT = "save_document"
    FINISHED = "finished"
    FAILED = "failed"


class ConsumerPluginMixin:
    def __init__(
        self,
        input_doc: ConsumableDocument,
        metadata: DocumentMetadataOverrides,
        status_mgr: ProgressManager,
        base_tmp_dir: Path,
        task_id: str,
    ) -> None:
        super().__init__(input_doc, metadata, status_mgr, base_tmp_dir, task_id)

        self.renew_logging_group()

        self.filename = self.metadata.filename or self.input_doc.original_file.name

    def _send_progress(
        self,
        current_progress: int,
        max_progress: int,
        status: ProgressStatusOptions,
        message: ConsumerStatusShortMessage | str | None = None,
        document_id=None,
    ):  # pragma: no cover
        self.status_mgr.send_progress(
            status,
            message,
            current_progress,
            max_progress,
            extra_args={
                "document_id": document_id,
                "owner_id": self.metadata.owner_id if self.metadata.owner_id else None,
                "users_can_view": (self.metadata.view_users or [])
                + (self.metadata.change_users or []),
                "groups_can_view": (self.metadata.view_groups or [])
                + (self.metadata.change_groups or []),
            },
        )

    def _fail(
        self,
        message: ConsumerStatusShortMessage | str,
        log_message: str | None = None,
        exc_info=None,
        exception: Exception | None = None,
    ):
        self._send_progress(100, 100, ProgressStatusOptions.FAILED, message)
        self.log.error(log_message or message, exc_info=exc_info)
        raise ConsumerError(f"{self.filename}: {log_message or message}") from exception


class ConsumerPlugin(
    AlwaysRunPluginMixin,
    NoSetupPluginMixin,
    NoCleanupPluginMixin,
    LoggingMixin,
    ConsumerPluginMixin,
    ConsumeTaskPlugin,
):
    logging_name = "paperless.consumer"

    def run_pre_consume_script(self):
        """
        If one is configured and exists, run the pre-consume script and
        handle its output and/or errors
        """
        if not settings.PRE_CONSUME_SCRIPT:
            return

        if not Path(settings.PRE_CONSUME_SCRIPT).is_file():
            self._fail(
                ConsumerStatusShortMessage.PRE_CONSUME_SCRIPT_NOT_FOUND,
                f"Configured pre-consume script "
                f"{settings.PRE_CONSUME_SCRIPT} does not exist.",
            )

        self.log.info(f"Executing pre-consume script {settings.PRE_CONSUME_SCRIPT}")

        working_file_path = str(self.working_copy)
        original_file_path = str(self.input_doc.original_file)

        script_env = os.environ.copy()
        script_env["DOCUMENT_SOURCE_PATH"] = original_file_path
        script_env["DOCUMENT_WORKING_PATH"] = working_file_path
        script_env["TASK_ID"] = self.task_id or ""

        try:
            run_subprocess(
                [
                    settings.PRE_CONSUME_SCRIPT,
                    original_file_path,
                ],
                script_env,
                self.log,
            )

        except Exception as e:
            self._fail(
                ConsumerStatusShortMessage.PRE_CONSUME_SCRIPT_ERROR,
                f"Error while executing pre-consume script: {e}",
                exc_info=True,
                exception=e,
            )

    def run_post_consume_script(self, document: Document):
        """
        If one is configured and exists, run the pre-consume script and
        handle its output and/or errors
        """
        if not settings.POST_CONSUME_SCRIPT:
            return

        if not Path(settings.POST_CONSUME_SCRIPT).is_file():
            self._fail(
                ConsumerStatusShortMessage.POST_CONSUME_SCRIPT_NOT_FOUND,
                f"Configured post-consume script "
                f"{settings.POST_CONSUME_SCRIPT} does not exist.",
            )

        self.log.info(
            f"Executing post-consume script {settings.POST_CONSUME_SCRIPT}",
        )

        script_env = os.environ.copy()

        script_env["DOCUMENT_ID"] = str(document.pk)
        script_env["DOCUMENT_TYPE"] = str(document.document_type)
        script_env["DOCUMENT_CREATED"] = str(document.created)
        script_env["DOCUMENT_MODIFIED"] = str(document.modified)
        script_env["DOCUMENT_ADDED"] = str(document.added)
        script_env["DOCUMENT_FILE_NAME"] = document.get_public_filename()
        script_env["DOCUMENT_SOURCE_PATH"] = os.path.normpath(document.source_path)
        script_env["DOCUMENT_ARCHIVE_PATH"] = os.path.normpath(
            str(document.archive_path),
        )
        script_env["DOCUMENT_THUMBNAIL_PATH"] = os.path.normpath(
            document.thumbnail_path,
        )
        script_env["DOCUMENT_DOWNLOAD_URL"] = reverse(
            "document-download",
            kwargs={"pk": document.pk},
        )
        script_env["DOCUMENT_THUMBNAIL_URL"] = reverse(
            "document-thumb",
            kwargs={"pk": document.pk},
        )
        script_env["DOCUMENT_OWNER"] = (
            document.owner.get_username() if document.owner else ""
        )
        script_env["DOCUMENT_CORRESPONDENT"] = str(document.correspondent)
        script_env["DOCUMENT_TAGS"] = str(
            ",".join(document.tags.all().values_list("name", flat=True)),
        )
        script_env["DOCUMENT_ORIGINAL_FILENAME"] = str(document.original_filename)
        script_env["TASK_ID"] = self.task_id or ""

        try:
            run_subprocess(
                [
                    settings.POST_CONSUME_SCRIPT,
                    str(document.pk),
                    document.get_public_filename(),
                    os.path.normpath(document.source_path),
                    os.path.normpath(document.thumbnail_path),
                    reverse("document-download", kwargs={"pk": document.pk}),
                    reverse("document-thumb", kwargs={"pk": document.pk}),
                    str(document.correspondent),
                    str(",".join(document.tags.all().values_list("name", flat=True))),
                ],
                script_env,
                self.log,
            )

        except Exception as e:
            self._fail(
                ConsumerStatusShortMessage.POST_CONSUME_SCRIPT_ERROR,
                f"Error while executing post-consume script: {e}",
                exc_info=True,
                exception=e,
            )

    def run(self) -> str:
        """
        Return the document object if it was successfully created.
        """

        tempdir = None

        try:
            # Preflight has already run including progress update to 0%
            self.log.info(f"Consuming {self.filename}")

            # For the actual work, copy the file into a tempdir
            tempdir = tempfile.TemporaryDirectory(
                prefix="paperless-ngx",
                dir=settings.SCRATCH_DIR,
            )
            self.working_copy = Path(tempdir.name) / Path(self.filename)
            copy_file_with_basic_stats(self.input_doc.original_file, self.working_copy)
            self.unmodified_original = None

            # Determine the parser class.

            mime_type = magic.from_file(self.working_copy, mime=True)

            self.log.debug(f"Detected mime type: {mime_type}")

            if (
                Path(self.filename).suffix.lower() == ".pdf"
                and mime_type in settings.CONSUMER_PDF_RECOVERABLE_MIME_TYPES
            ):
                try:
                    # The file might be a pdf, but the mime type is wrong.
                    # Try to clean with qpdf
                    self.log.debug(
                        "Detected possible PDF with wrong mime type, trying to clean with qpdf",
                    )
                    run_subprocess(
                        [
                            "qpdf",
                            "--replace-input",
                            self.working_copy,
                        ],
                        logger=self.log,
                    )
                    mime_type = magic.from_file(self.working_copy, mime=True)
                    self.log.debug(f"Detected mime type after qpdf: {mime_type}")
                    # Save the original file for later
                    self.unmodified_original = (
                        Path(tempdir.name) / Path("uo") / Path(self.filename)
                    )
                    self.unmodified_original.parent.mkdir(exist_ok=True)
                    copy_file_with_basic_stats(
                        self.input_doc.original_file,
                        self.unmodified_original,
                    )
                except Exception as e:
                    self.log.error(f"Error attempting to clean PDF: {e}")

            # Based on the mime type, get the parser for that type
            parser_class: type[DocumentParser] | None = get_parser_class_for_mime_type(
                mime_type,
            )
            if not parser_class:
                tempdir.cleanup()
                self._fail(
                    ConsumerStatusShortMessage.UNSUPPORTED_TYPE,
                    f"Unsupported mime type {mime_type}",
                )

            # Notify all listeners that we're going to do some work.

            document_consumption_started.send(
                sender=self.__class__,
                filename=self.working_copy,
                logging_group=self.logging_group,
            )

            self.run_pre_consume_script()
        except:
            if tempdir:
                tempdir.cleanup()
            raise

        def progress_callback(current_progress, max_progress):  # pragma: no cover
            # recalculate progress to be within 20 and 80
            p = int((current_progress / max_progress) * 50 + 20)
            self._send_progress(p, 100, ProgressStatusOptions.WORKING)

        # This doesn't parse the document yet, but gives us a parser.

        document_parser: DocumentParser = parser_class(
            self.logging_group,
            progress_callback=progress_callback,
        )

        self.log.debug(f"Parser: {type(document_parser).__name__}")

        # Parse the document. This may take some time.

        text = None
        date = None
        thumbnail = None
        archive_path = None
        page_count = None

        try:
            self._send_progress(
                20,
                100,
                ProgressStatusOptions.WORKING,
                ConsumerStatusShortMessage.PARSING_DOCUMENT,
            )
            self.log.debug(f"Parsing {self.filename}...")
            if (
                isinstance(document_parser, MailDocumentParser)
                and self.input_doc.mailrule_id
            ):
                document_parser.parse(
                    self.working_copy,
                    mime_type,
                    self.filename,
                    self.input_doc.mailrule_id,
                )
            else:
                document_parser.parse(self.working_copy, mime_type, self.filename)

            self.log.debug(f"Generating thumbnail for {self.filename}...")
            self._send_progress(
                70,
                100,
                ProgressStatusOptions.WORKING,
                ConsumerStatusShortMessage.GENERATING_THUMBNAIL,
            )
            thumbnail = document_parser.get_thumbnail(
                self.working_copy,
                mime_type,
                self.filename,
            )

            text = document_parser.get_text()
            date = document_parser.get_date()
            if date is None:
                self._send_progress(
                    90,
                    100,
                    ProgressStatusOptions.WORKING,
                    ConsumerStatusShortMessage.PARSE_DATE,
                )
                date = parse_date(self.filename, text)
            archive_path = document_parser.get_archive_path()
            page_count = document_parser.get_page_count(self.working_copy, mime_type)

        except ParseError as e:
            document_parser.cleanup()
            if tempdir:
                tempdir.cleanup()
            self._fail(
                str(e),
                f"Error occurred while consuming document {self.filename}: {e}",
                exc_info=True,
                exception=e,
            )
        except Exception as e:
            document_parser.cleanup()
            if tempdir:
                tempdir.cleanup()
            self._fail(
                str(e),
                f"Unexpected error while consuming document {self.filename}: {e}",
                exc_info=True,
                exception=e,
            )

        # Prepare the document classifier.

        # TODO: I don't really like to do this here, but this way we avoid
        #   reloading the classifier multiple times, since there are multiple
        #   post-consume hooks that all require the classifier.

        classifier = load_classifier()

        self._send_progress(
            95,
            100,
            ProgressStatusOptions.WORKING,
            ConsumerStatusShortMessage.SAVE_DOCUMENT,
        )
        # now that everything is done, we can start to store the document
        # in the system. This will be a transaction and reasonably fast.
        try:
            with transaction.atomic():
                # store the document.
                document = self._store(
                    text=text,
                    date=date,
                    page_count=page_count,
                    mime_type=mime_type,
                )

                # If we get here, it was successful. Proceed with post-consume
                # hooks. If they fail, nothing will get changed.

                document_consumption_finished.send(
                    sender=self.__class__,
                    document=document,
                    logging_group=self.logging_group,
                    classifier=classifier,
                    original_file=self.unmodified_original
                    if self.unmodified_original
                    else self.working_copy,
                )

                # After everything is in the database, copy the files into
                # place. If this fails, we'll also rollback the transaction.
                with FileLock(settings.MEDIA_LOCK):
                    document.filename = generate_unique_filename(document)
                    create_source_path_directory(document.source_path)

                    self._write(
                        document.storage_type,
                        self.unmodified_original
                        if self.unmodified_original is not None
                        else self.working_copy,
                        document.source_path,
                    )

                    self._write(
                        document.storage_type,
                        thumbnail,
                        document.thumbnail_path,
                    )

                    if archive_path and Path(archive_path).is_file():
                        document.archive_filename = generate_unique_filename(
                            document,
                            archive_filename=True,
                        )
                        create_source_path_directory(document.archive_path)
                        self._write(
                            document.storage_type,
                            archive_path,
                            document.archive_path,
                        )

                        with Path(archive_path).open("rb") as f:
                            document.archive_checksum = hashlib.md5(
                                f.read(),
                            ).hexdigest()

                # Don't save with the lock active. Saving will cause the file
                # renaming logic to acquire the lock as well.
                # This triggers things like file renaming
                document.save()

                # RKC: Attach email metadata as custom fields if document came from mail
                if any([
                    self.input_doc.mail_uid,
                    self.input_doc.mail_from,
                    self.input_doc.mail_sender,
                    self.input_doc.mail_subject,
                    self.input_doc.mail_date,
                ]):
                    _attach_mail_metadata_custom_fields(
                        document,
                        mail_uid=self.input_doc.mail_uid,
                        mail_from=self.input_doc.mail_from,
                        mail_sender=self.input_doc.mail_sender,
                        mail_subject=self.input_doc.mail_subject,
                        mail_date=self.input_doc.mail_date,
                    )
                # /end RKC edit

                # Delete the file only if it was successfully consumed
                self.log.debug(f"Deleting original file {self.input_doc.original_file}")
                self.input_doc.original_file.unlink()
                self.log.debug(f"Deleting working copy {self.working_copy}")
                self.working_copy.unlink()
                if self.unmodified_original is not None:  # pragma: no cover
                    self.log.debug(
                        f"Deleting unmodified original file {self.unmodified_original}",
                    )
                    self.unmodified_original.unlink()

                # https://github.com/jonaswinkler/paperless-ng/discussions/1037
                shadow_file = (
                    Path(self.input_doc.original_file).parent
                    / f"._{Path(self.input_doc.original_file).name}"
                )

                if Path(shadow_file).is_file():
                    self.log.debug(f"Deleting shadow file {shadow_file}")
                    Path(shadow_file).unlink()

        except Exception as e:
            self._fail(
                str(e),
                f"The following error occurred while storing document "
                f"{self.filename} after parsing: {e}",
                exc_info=True,
                exception=e,
            )
        finally:
            document_parser.cleanup()
            tempdir.cleanup()

        self.run_post_consume_script(document)

        self.log.info(f"Document {document} consumption finished")

        self._send_progress(
            100,
            100,
            ProgressStatusOptions.SUCCESS,
            ConsumerStatusShortMessage.FINISHED,
            document.id,
        )

        # Return the most up to date fields
        document.refresh_from_db()

        return f"Success. New document id {document.pk} created"

    def _parse_title_placeholders(self, title: str) -> str:
        local_added = timezone.localtime(timezone.now())

        correspondent_name = (
            Correspondent.objects.get(pk=self.metadata.correspondent_id).name
            if self.metadata.correspondent_id is not None
            else None
        )
        doc_type_name = (
            DocumentType.objects.get(pk=self.metadata.document_type_id).name
            if self.metadata.document_type_id is not None
            else None
        )
        owner_username = (
            User.objects.get(pk=self.metadata.owner_id).username
            if self.metadata.owner_id is not None
            else None
        )

        return parse_w_workflow_placeholders(
            title,
            correspondent_name,
            doc_type_name,
            owner_username,
            local_added,
            self.filename,
            self.filename,
        )

    def _store(
        self,
        text: str,
        date: datetime.datetime | None,
        page_count: int | None,
        mime_type: str,
    ) -> Document:
        # If someone gave us the original filename, use it instead of doc.

        self.log.debug("Saving record to database")

        if self.metadata.created is not None:
            create_date = self.metadata.created
            self.log.debug(
                f"Creation date from post_documents parameter: {create_date}",
            )
        elif date is not None:
            create_date = date
            self.log.debug(f"Creation date from parse_date: {create_date}")
        else:
            stats = Path(self.input_doc.original_file).stat()
            create_date = timezone.make_aware(
                datetime.datetime.fromtimestamp(stats.st_mtime),
            )
            self.log.debug(f"Creation date from st_mtime: {create_date}")

        storage_type = Document.STORAGE_TYPE_UNENCRYPTED

        if self.metadata.filename:
            title = Path(self.metadata.filename).stem
        else:
            title = self.input_doc.original_file.stem

        if self.metadata.title is not None:
            try:
                title = self._parse_title_placeholders(self.metadata.title)
            except Exception as e:
                self.log.error(
                    f"Error occurred parsing title override '{self.metadata.title}', falling back to original. Exception: {e}",
                )

        file_for_checksum = (
            self.unmodified_original
            if self.unmodified_original is not None
            else self.working_copy
        )

        document = Document.objects.create(
            title=title[:127],
            content=text,
            mime_type=mime_type,
            checksum=hashlib.md5(file_for_checksum.read_bytes()).hexdigest(),
            created=create_date,
            modified=create_date,
            storage_type=storage_type,
            page_count=page_count,
            original_filename=self.filename,
        )

        self.apply_overrides(document)

        document.save()

        return document

    def apply_overrides(self, document):
        if self.metadata.correspondent_id:
            document.correspondent = Correspondent.objects.get(
                pk=self.metadata.correspondent_id,
            )

        if self.metadata.document_type_id:
            document.document_type = DocumentType.objects.get(
                pk=self.metadata.document_type_id,
            )

        if self.metadata.tag_ids:
            for tag_id in self.metadata.tag_ids:
                document.add_nested_tags([Tag.objects.get(pk=tag_id)])

        if self.metadata.storage_path_id:
            document.storage_path = StoragePath.objects.get(
                pk=self.metadata.storage_path_id,
            )

        if self.metadata.asn is not None:
            document.archive_serial_number = self.metadata.asn

        if self.metadata.owner_id:
            document.owner = User.objects.get(
                pk=self.metadata.owner_id,
            )

        if (
            self.metadata.view_users is not None
            or self.metadata.view_groups is not None
            or self.metadata.change_users is not None
            or self.metadata.change_users is not None
        ):
            permissions = {
                "view": {
                    "users": self.metadata.view_users or [],
                    "groups": self.metadata.view_groups or [],
                },
                "change": {
                    "users": self.metadata.change_users or [],
                    "groups": self.metadata.change_groups or [],
                },
            }
            set_permissions_for_object(permissions=permissions, object=document)

        if self.metadata.custom_fields:
            for field in CustomField.objects.filter(
                id__in=self.metadata.custom_fields.keys(),
            ).distinct():
                value_field_name = CustomFieldInstance.get_value_field_name(
                    data_type=field.data_type,
                )
                args = {
                    "field": field,
                    "document": document,
                    value_field_name: self.metadata.custom_fields.get(field.id, None),
                }
                CustomFieldInstance.objects.create(**args)  # adds to document

    def _write(self, storage_type, source, target):
        with (
            Path(source).open("rb") as read_file,
            Path(target).open("wb") as write_file,
        ):
            write_file.write(read_file.read())

        # Attempt to copy file's original stats, but it's ok if we can't
        try:
            copy_basic_file_stats(source, target)
        except Exception:  # pragma: no cover
            pass


class ConsumerPreflightPlugin(
    NoCleanupPluginMixin,
    NoSetupPluginMixin,
    AlwaysRunPluginMixin,
    LoggingMixin,
    ConsumerPluginMixin,
    ConsumeTaskPlugin,
):
    NAME: str = "ConsumerPreflightPlugin"
    logging_name = "paperless.consumer"

    def pre_check_file_exists(self):
        """
        Confirm the input file still exists where it should
        """
        if TYPE_CHECKING:
            assert isinstance(self.input_doc.original_file, Path), (
                self.input_doc.original_file
            )
        if not self.input_doc.original_file.is_file():
            self._fail(
                ConsumerStatusShortMessage.FILE_NOT_FOUND,
                f"Cannot consume {self.input_doc.original_file}: File not found.",
            )

    def pre_check_duplicate(self):
        """
        Using the MD5 of the file, check this exact file doesn't already exist
        """
        with Path(self.input_doc.original_file).open("rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        existing_doc = Document.global_objects.filter(
            Q(checksum=checksum) | Q(archive_checksum=checksum),
        )

        # RKC: Secondary dedup for EML documents using Mail UID custom field
        # Checksum-based dedup doesn't work for EML files because the same email
        # can produce different byte representations across fetches (header
        # reordering, MIME boundary regeneration, line ending normalization).
        # Fall back to Mail UID matching for mail-sourced EML files only —
        # attachments (PDFs etc.) share the same mail_uid but have stable
        # checksums, so they are handled by Tier 1 above.
        is_eml_file = Path(self.filename).suffix.lower() == '.eml'
        self.log.info(
            f"Dedup Tier 2 check: filename='{self.filename}', "
            f"is_eml={is_eml_file}, "
            f"mail_uid='{self.input_doc.mail_uid}', "
            f"checksum_match={existing_doc.exists()}"
        )
        if not existing_doc.exists() and self.input_doc.mail_uid and is_eml_file:
            try:
                mail_uid_field_name = settings.PAPERLESS_MAIL_CORRELATION_FIELD
                uid_field = CustomField.objects.filter(
                    name=mail_uid_field_name,
                ).first()
                self.log.info(
                    f"Dedup Tier 2: looking up field "
                    f"'{mail_uid_field_name}' → "
                    f"{'found (pk=' + str(uid_field.pk) + ')' if uid_field else 'NOT FOUND'}"
                )
                if uid_field:
                    # Use global_objects to include soft-deleted instances
                    # (trashed documents cascade soft-delete to their custom
                    # field instances, hiding them from the default manager)
                    uid_match = CustomFieldInstance.global_objects.filter(
                        field=uid_field,
                        value_text=self.input_doc.mail_uid,
                    ).select_related('document').first()
                    self.log.info(
                        f"Dedup Tier 2: queried value_text="
                        f"'{self.input_doc.mail_uid}' → "
                        f"{'match doc #' + str(uid_match.document.pk) if uid_match else 'NO MATCH'}"
                    )
                    if uid_match:
                        existing_doc = Document.global_objects.filter(
                            pk=uid_match.document.pk,
                        )
                        self.log.info(
                            f"EML duplicate detected via Mail UID "
                            f"'{self.input_doc.mail_uid}' "
                            f"matching document #{uid_match.document.pk}"
                        )
            except Exception as e:
                self.log.warning(f"Mail UID dedup lookup failed: {e}", exc_info=True)
        # /end RKC edit

        if existing_doc.exists():
            # RKC: Re-add duplicate documents instead of just failing
            # When enabled, resets the "added" date so the document surfaces again,
            # optionally tags it and adds an informational note.
            # Also handles trashed duplicates: restores them, applies re-add logic,
            # and optionally re-trashes them (CONSUMER_READD_RETRASH).
            if settings.CONSUMER_READD_DOCUMENTS:
                self._handle_readd(existing_doc.get())
                if settings.CONSUMER_DELETE_DUPLICATES:
                    Path(self.input_doc.original_file).unlink()
                raise StopConsumeTaskError(
                    f"Re-added duplicate document #{existing_doc.get().pk} "
                    f"'{existing_doc.get().title}'"
                )
            # /end RKC edit

            msg = ConsumerStatusShortMessage.DOCUMENT_ALREADY_EXISTS
            log_msg = f"Not consuming {self.filename}: It is a duplicate of {existing_doc.get().title} (#{existing_doc.get().pk})."

            if existing_doc.first().deleted_at is not None:
                msg = ConsumerStatusShortMessage.DOCUMENT_ALREADY_EXISTS_IN_TRASH
                log_msg += " Note: existing document is in the trash."

            if settings.CONSUMER_DELETE_DUPLICATES:
                Path(self.input_doc.original_file).unlink()
            self._fail(
                msg,
                log_msg,
            )

    # RKC: Re-add handler for duplicate documents
    def _handle_readd(self, existing_doc: Document):
        """
        Re-adds an existing document by resetting its 'added' date, optionally
        tagging it and adding an informational note. This is useful when reminder
        emails arrive with the same invoice attachment — instead of silently
        failing, the document surfaces at the top of the inbox again.

        If the document is in the trash (soft-deleted), it is restored first
        because the checksum field has a DB-level UNIQUE constraint, making it
        impossible to create a second document with the same checksum. After
        re-add logic is applied, the document is optionally re-trashed if
        CONSUMER_READD_RETRASH is enabled.
        """
        now = timezone.now()
        old_added = timezone.localtime(existing_doc.added)
        new_added = timezone.localtime(now)
        was_trashed = existing_doc.deleted_at is not None

        # Restore from trash if needed (checksum UNIQUE constraint prevents
        # creating a new document, so we must work with the existing one).
        # Must also restore related soft-deleted records: CustomFieldInstance
        # and Note both inherit SoftDeleteModel, so trashing the document
        # cascades soft-delete to them as well.
        if was_trashed:
            Document.global_objects.filter(pk=existing_doc.pk).update(
                deleted_at=None,
            )
            # Restore soft-deleted custom field instances
            cf_restored = CustomFieldInstance.deleted_objects.filter(
                document_id=existing_doc.pk,
            ).update(deleted_at=None)
            # Restore soft-deleted notes
            notes_restored = Note.deleted_objects.filter(
                document_id=existing_doc.pk,
            ).update(deleted_at=None)
            self.log.info(
                f"Restored document #{existing_doc.pk} "
                f"'{existing_doc.title}' from trash for re-add "
                f"(+{cf_restored} custom fields, +{notes_restored} notes)"
            )

        # Reset the 'added' timestamp via .update() to bypass auto_now_add
        Document.objects.filter(pk=existing_doc.pk).update(added=now)

        self.log.info(
            f"Re-added document #{existing_doc.pk} "
            f"'{existing_doc.title}' (added date reset to {new_added})"
        )

        # Apply the re-add tag if configured
        if settings.CONSUMER_READD_TAG_ID is not None:
            try:
                tag = Tag.objects.get(pk=settings.CONSUMER_READD_TAG_ID)
                existing_doc.tags.add(tag)
                self.log.info(
                    f"Tagged document #{existing_doc.pk} with '{tag.name}'"
                )
            except Tag.DoesNotExist:
                self.log.warning(
                    f"CONSUMER_READD_TAG_ID={settings.CONSUMER_READD_TAG_ID} "
                    f"not found, skipping tag"
                )

        # Add an informational note if enabled
        if settings.CONSUMER_READD_ADD_NOTE:
            source_info = self._build_readd_source_info()
            storage_path_name = (
                existing_doc.storage_path.name
                if existing_doc.storage_path
                else "Default"
            )

            note_text = (
                f"Originally added:  {old_added.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Re-added:  {new_added.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"In:  {storage_path_name}"
            )
            if was_trashed:
                note_text += "\nRestored from trash"
                if settings.CONSUMER_READD_RETRASH:
                    note_text += " (will be re-trashed)"
            if source_info:
                note_text += f"\n{source_info}"

            Note.objects.create(
                note=note_text,
                document=existing_doc,
            )
            self.log.debug(
                f"Added re-add note to document #{existing_doc.pk}"
            )

        # Re-trash the document if it was trashed and retrash is enabled
        if was_trashed and settings.CONSUMER_READD_RETRASH:
            Document.objects.filter(pk=existing_doc.pk).update(
                deleted_at=timezone.now(),
            )
            self.log.info(
                f"Re-trashed document #{existing_doc.pk} after re-add "
                f"(CONSUMER_READD_RETRASH enabled)"
            )

    def _build_readd_source_info(self) -> str:
        """
        Builds a human-readable string describing the source of the duplicate
        document that triggered the re-add. For mail sources, includes the
        Mail UID and subject; for other sources, includes the source type
        and filename.
        """
        source = self.input_doc.source

        if source == DocumentSource.MailFetch:
            parts = []
            if self.input_doc.mail_uid:
                parts.append(f"Mail UID: {self.input_doc.mail_uid}")
            if self.input_doc.mail_subject:
                parts.append(f"Subject: {self.input_doc.mail_subject}")
            if self.input_doc.mail_from:
                parts.append(f"From: {self.input_doc.mail_from}")
            return "\n".join(parts) if parts else "Source: Mail"

        source_names = {
            DocumentSource.ConsumeFolder: "Consume Folder",
            DocumentSource.ApiUpload: "API Upload",
            DocumentSource.WebUI: "Web UI",
        }
        source_name = source_names.get(source, f"Unknown ({source})")
        return f"Source: {source_name}\nFile: {self.filename}"
    # /end RKC edit

    def pre_check_directories(self):
        """
        Ensure all required directories exist before attempting to use them
        """
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        settings.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
        settings.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
        settings.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    def pre_check_asn_value(self):
        """
        Check that if override_asn is given, it is unique and within a valid range
        """
        if self.metadata.asn is None:
            # check not necessary in case no ASN gets set
            return
        # Validate the range is above zero and less than uint32_t max
        # otherwise, Whoosh can't handle it in the index
        if (
            self.metadata.asn < Document.ARCHIVE_SERIAL_NUMBER_MIN
            or self.metadata.asn > Document.ARCHIVE_SERIAL_NUMBER_MAX
        ):
            self._fail(
                ConsumerStatusShortMessage.ASN_RANGE,
                f"Not consuming {self.filename}: "
                f"Given ASN {self.metadata.asn} is out of range "
                f"[{Document.ARCHIVE_SERIAL_NUMBER_MIN:,}, "
                f"{Document.ARCHIVE_SERIAL_NUMBER_MAX:,}]",
            )
        existing_asn_doc = Document.global_objects.filter(
            archive_serial_number=self.metadata.asn,
        )
        if existing_asn_doc.exists():
            msg = ConsumerStatusShortMessage.ASN_ALREADY_EXISTS
            log_msg = f"Not consuming {self.filename}: Given ASN {self.metadata.asn} already exists!"

            if existing_asn_doc.first().deleted_at is not None:
                msg = ConsumerStatusShortMessage.ASN_ALREADY_EXISTS_IN_TRASH
                log_msg += " Note: existing document is in the trash."

            self._fail(
                msg,
                log_msg,
            )

    def run(self) -> None:
        self._send_progress(
            0,
            100,
            ProgressStatusOptions.STARTED,
            ConsumerStatusShortMessage.NEW_FILE,
        )

        # Make sure that preconditions for consuming the file are met.

        self.pre_check_file_exists()
        self.pre_check_duplicate()
        self.pre_check_directories()
        self.pre_check_asn_value()
