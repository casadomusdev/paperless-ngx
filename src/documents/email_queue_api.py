"""
RKC: Pending Email Queue REST API (v1.5.0)
Provides list, retrieve, and bulk_delete endpoints for the PendingEmail queue.
Only accessible to admin/superuser accounts.
"""
from django_filters import CharFilter, FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from documents.email_queue import PendingEmail
from documents.serialisers import StandardPagination


class PendingEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingEmail
        fields = [
            "id", "action", "document",
            "subject_template", "rendered_to",
            "status", "attempts", "max_attempts",
            "next_retry_at", "last_error",
            "created_at", "updated_at",
        ]


class PendingEmailFilterSet(FilterSet):
    filter_text = CharFilter(method="filter_by_text")

    class Meta:
        model = PendingEmail
        fields = {
            "status": ["exact"],
        }

    def filter_by_text(self, queryset, name, value):
        if not value or len(value) < 3:
            return queryset
        filter_field = self.request.query_params.get("filter_field", "last_error")
        if filter_field == "subject":
            return queryset.filter(subject_template__icontains=value)
        elif filter_field == "recipients":
            return queryset.filter(rendered_to__icontains=value)
        elif filter_field == "status":
            return queryset.filter(status__icontains=value)
        else:
            return queryset.filter(last_error__icontains=value)


class PendingEmailViewSet(ReadOnlyModelViewSet):
    serializer_class = PendingEmailSerializer
    permission_classes = (IsAdminUser,)
    pagination_class = StandardPagination
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = PendingEmailFilterSet
    queryset = PendingEmail.objects.all().order_by("-created_at")

    @action(methods=["post"], detail=False)
    def bulk_delete(self, request):
        delete_all = request.data.get("delete_all", False)

        if delete_all:
            filter_field = request.data.get("filter_field", "")
            filter_text = request.data.get("filter_text", "")
            qs = PendingEmail.objects.all()
            if filter_text and len(filter_text) >= 3:
                if filter_field == "last_error":
                    qs = qs.filter(last_error__icontains=filter_text)
                elif filter_field == "subject":
                    qs = qs.filter(subject_template__icontains=filter_text)
                elif filter_field == "recipients":
                    qs = qs.filter(rendered_to__icontains=filter_text)
                elif filter_field == "status":
                    qs = qs.filter(status__icontains=filter_text)
            count = qs.count()
            qs.delete()
            return Response({"result": "OK", "deleted": count})
        else:
            ids = request.data.get("ids", [])
            if not isinstance(ids, list):
                return Response({"error": "ids must be a list"}, status=400)
            count = PendingEmail.objects.filter(id__in=ids).delete()[0]
            return Response({"result": "OK", "deleted": count})
# /end RKC edit
