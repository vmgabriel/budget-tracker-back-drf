"""DRF input and output serializers for dashboard queries."""

from datetime import date
from typing import cast

from rest_framework import serializers

from apps.dashboard.domain.value_objects import PERIOD_CHOICES


class DashboardQuerySerializer(serializers.Serializer):
    """Validate an optional bounded dashboard date range."""

    period = serializers.ChoiceField(
        choices=PERIOD_CHOICES,
        required=False,
        help_text="Granularity for the generic dashboard endpoint; defaults to weekly.",
    )
    start_date = serializers.DateField(
        required=False,
        help_text="Inclusive range start; ranges are limited to 366 days.",
    )
    end_date = serializers.DateField(
        required=False,
        help_text="Inclusive range end; ranges are limited to 366 days.",
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Reject an explicitly reversed date range before querying."""
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if (
            start_date is not None
            and end_date is not None
            and cast(date, start_date) > cast(date, end_date)
        ):
            raise serializers.ValidationError(
                "start_date must not be later than end_date."
            )
        return attrs


class DashboardSummarySerializer(serializers.Serializer):
    """Represent one safe pre-computed dashboard summary."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    period = serializers.ChoiceField(choices=PERIOD_CHOICES, read_only=True)
    date = serializers.DateField(source="summary_date.value", read_only=True)
    total_income = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        source="total_income.amount",
        read_only=True,
    )
    total_expense = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        source="total_expense.amount",
        read_only=True,
    )
    net_balance = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        source="net_balance.amount",
        read_only=True,
    )
    generated_at = serializers.DateTimeField(read_only=True)
    is_stale = serializers.BooleanField(read_only=True)
    stale_at = serializers.DateTimeField(read_only=True, allow_null=True)
    status = serializers.ChoiceField(
        choices=(("fresh", "Fresh"), ("stale", "Stale")),
        read_only=True,
    )


class DashboardListSerializer(serializers.Serializer):
    """Represent a bounded list of pre-computed dashboard summaries."""

    period = serializers.ChoiceField(choices=PERIOD_CHOICES, read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    summary_count = serializers.IntegerField(read_only=True)
    is_empty = serializers.BooleanField(read_only=True)
    has_stale_data = serializers.BooleanField(read_only=True)
    summaries = DashboardSummarySerializer(many=True, read_only=True)


class DashboardOverviewSerializer(serializers.Serializer):
    """Represent the three current pre-computed dashboard snapshots."""

    as_of_date = serializers.DateField(read_only=True)
    today = DashboardSummarySerializer(allow_null=True, read_only=True)
    this_week = DashboardSummarySerializer(allow_null=True, read_only=True)
    this_month = DashboardSummarySerializer(allow_null=True, read_only=True)
