import logging
import uuid


# RKC: Custom formatter that includes the consume task correlation ID (group)
# when available. Non-consumer log entries get a dash instead.
class CorrelatedFormatter(logging.Formatter):
    """
    Extends the standard Formatter to safely include the 'group' extra
    from LoggingMixin. Shows the first 8 chars of the UUID for readability.
    Log lines from non-consumer code (which don't have a group) get '-'.
    """

    def format(self, record):
        if hasattr(record, "group") and record.group:
            record.group_short = str(record.group)[:8]
        else:
            record.group_short = "-"
        return super().format(record)
# /end RKC edit


class LoggingMixin:
    def renew_logging_group(self):
        """
        Creates a new UUID to group subsequent log calls together with
        the extra data named group
        """
        self.logging_group = uuid.uuid4()
        self.log = logging.LoggerAdapter(
            logging.getLogger(self.logging_name),
            extra={"group": self.logging_group},
        )
