from django_filters import CharFilter
from django_filters import FilterSet

from paperless_mail.models import ProcessedMail


class ProcessedMailFilterSet(FilterSet):
    # RKC: Add server-side text filtering support for processed mail
    # Allows filtering across entire dataset, not just current page
    filter_text = CharFilter(method="filter_by_text")
    # /end RKC edit

    class Meta:
        model = ProcessedMail
        fields = {
            "rule": ["exact"],
            "status": ["exact"],
        }

    # RKC: Custom filter method that applies text search to specified field
    # Supports filtering on error, subject, received, and processed fields
    def filter_by_text(self, queryset, name, value):
        """
        Filter the queryset based on filter_field and filter_text parameters.
        Uses case-insensitive contains search (__icontains).
        """
        if not value or len(value) < 3:
            # Require at least 3 characters for performance
            return queryset

        filter_field = self.request.query_params.get("filter_field", "error")

        if filter_field == "error":
            return queryset.filter(error__icontains=value)
        elif filter_field == "subject":
            return queryset.filter(subject__icontains=value)
        elif filter_field == "received":
            # For datetime fields, convert to string and search
            # This allows searching formatted dates like "2025-01"
            return queryset.filter(received__icontains=value)
        elif filter_field == "processed":
            return queryset.filter(processed__icontains=value)
        else:
            # Default to error field if unknown filter_field
            return queryset.filter(error__icontains=value)
    # /end RKC edit
