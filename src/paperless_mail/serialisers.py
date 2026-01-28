from rest_framework import serializers

from documents.serialisers import CorrespondentField
from documents.serialisers import DocumentTypeField
from documents.serialisers import OwnedObjectSerializer
from documents.serialisers import TagsField
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule
from paperless_mail.models import ProcessedMail


class ObfuscatedPasswordField(serializers.CharField):
    """
    Sends *** string instead of password in the clear
    """

    def to_representation(self, value) -> str:
        return "*" * max(10, len(value))

    def to_internal_value(self, data):
        return data


class MailAccountSerializer(OwnedObjectSerializer):
    password = ObfuscatedPasswordField()
    # RKC: SMTP sending fields (v1.1.0) - supports both OAuth2 and traditional SMTP
    use_for_sending = serializers.BooleanField(required=False, default=False)
    from_address = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    smtp_server = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    smtp_port = serializers.IntegerField(required=False, allow_null=True)
    smtp_security = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    smtp_username = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    smtp_password = ObfuscatedPasswordField(required=False, allow_blank=True, allow_null=True)
    sending_account_info = serializers.SerializerMethodField()
    # /end RKC edit

    class Meta:
        model = MailAccount
        fields = [
            "id",
            "name",
            "imap_server",
            "imap_port",
            "imap_security",
            "username",
            "password",
            "character_set",
            "is_token",
            "owner",
            "user_can_change",
            "permissions",
            "set_permissions",
            "account_type",
            "expiration",
            # RKC: SMTP sending fields (v1.1.0)
            "use_for_sending",
            "from_address",
            "smtp_server",
            "smtp_port",
            "smtp_security",
            "smtp_username",
            "smtp_password",
            "sending_account_info",
            # /end RKC edit
        ]
    
    # RKC: Return info about sending account changes (v1.1.0)
    def get_sending_account_info(self, obj):
        """Return information if this account replaced another as the sending account"""
        if hasattr(obj, '_sending_account_changed_from'):
            return {
                'changed': True,
                'previous_account': obj._sending_account_changed_from.name,
                'previous_account_id': obj._sending_account_changed_from.id,
            }
        return None
    # /end RKC edit

    def update(self, instance, validated_data):
        # RKC: Handle obfuscated passwords for both IMAP and SMTP (v1.1.0)
        if (
            "password" in validated_data
            and len(validated_data.get("password").replace("*", "")) == 0
        ):
            validated_data.pop("password")
        
        if (
            "smtp_password" in validated_data
            and validated_data.get("smtp_password")
            and len(validated_data.get("smtp_password").replace("*", "")) == 0
        ):
            validated_data.pop("smtp_password")
        # /end RKC edit
        
        super().update(instance, validated_data)
        return instance


class AccountField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return MailAccount.objects.all().order_by("-id")


class MailRuleSerializer(OwnedObjectSerializer):
    account = AccountField(required=True)
    action_parameter = serializers.CharField(
        allow_null=True,
        required=False,
        default="",
    )
    assign_correspondent = CorrespondentField(allow_null=True, required=False)
    assign_tags = TagsField(many=True, allow_null=True, required=False)
    assign_document_type = DocumentTypeField(allow_null=True, required=False)
    order = serializers.IntegerField(required=False)

    class Meta:
        model = MailRule
        fields = [
            "id",
            "name",
            "account",
            "enabled",
            "folder",
            "filter_from",
            "filter_to",
            "filter_subject",
            "filter_body",
            "filter_attachment_filename_include",
            "filter_attachment_filename_exclude",
            "maximum_age",
            "action",
            "action_parameter",
            "assign_title_from",
            "assign_tags",
            "assign_correspondent_from",
            "assign_correspondent",
            "assign_document_type",
            "assign_owner_from_rule",
            "order",
            "attachment_type",
            "consumption_scope",
            "pdf_layout",
            "owner",
            "user_can_change",
            "permissions",
            "set_permissions",
        ]

    def update(self, instance, validated_data):
        super().update(instance, validated_data)
        return instance

    def create(self, validated_data):
        assign_tags = validated_data.pop("assign_tags", [])
        mail_rule = super().create(validated_data)
        if assign_tags:
            mail_rule.assign_tags.set(assign_tags)
        return mail_rule

    def validate(self, attrs):
        action = attrs.get("action")
        action_parameter = attrs.get("action_parameter")

        if (
            action in [MailRule.MailAction.TAG, MailRule.MailAction.MOVE]
            and not action_parameter
        ):
            raise serializers.ValidationError("An action parameter is required.")

        return attrs

    def validate_maximum_age(self, value):
        if value > 36500:  # ~100 years
            raise serializers.ValidationError("Maximum mail age is unreasonably large.")
        return value


class ProcessedMailSerializer(OwnedObjectSerializer):
    class Meta:
        model = ProcessedMail
        fields = [
            "id",
            "owner",
            "rule",
            "folder",
            "uid",
            "subject",
            "received",
            "processed",
            "status",
            "error",
        ]
