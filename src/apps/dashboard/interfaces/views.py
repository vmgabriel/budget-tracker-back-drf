"""Authenticated HTTP interface for pre-computed dashboard data."""

from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.application.exceptions import InvalidDashboardQuery
from apps.dashboard.application.use_cases import GetUserDashboardCommand
from apps.dashboard.domain.value_objects import Period
from apps.dashboard.interfaces.dependencies import build_dashboard_use_cases
from apps.dashboard.interfaces.serializers import (
    DashboardListSerializer,
    DashboardOverviewSerializer,
    DashboardQuerySerializer,
    DashboardSummarySerializer,
)
from config.serializers import ERROR_RESPONSES


class DashboardOverviewView(APIView):
    """Return today's, this week's, and this month's persisted snapshots."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={status.HTTP_200_OK: DashboardOverviewSerializer, **ERROR_RESPONSES}
    )
    def get(self, request: Request) -> Response:
        result = build_dashboard_use_cases().overview.execute(
            _authenticated_user_id(request)
        )
        return Response(DashboardOverviewSerializer(result).data)


class DashboardView(APIView):
    """Return only persisted summaries; the HTTP read path performs no aggregation."""

    permission_classes = (IsAuthenticated,)
    fixed_period: Period | None = None

    @extend_schema(
        parameters=[DashboardQuerySerializer],
        responses={status.HTTP_200_OK: DashboardListSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        """List daily, weekly, or monthly summaries for the current user."""
        serializer = DashboardQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        requested_period = data.get("period")
        if (
            self.fixed_period is not None
            and requested_period is not None
            and str(requested_period) != self.fixed_period.value
        ):
            raise ValidationError(
                {"period": f"This endpoint only accepts {self.fixed_period.value}."}
            )
        period = self.fixed_period or Period(str(requested_period or "weekly"))

        try:
            result = build_dashboard_use_cases().get.execute(
                GetUserDashboardCommand(
                    user_id=_authenticated_user_id(request),
                    period=period,
                    start_date=data.get("start_date"),
                    end_date=data.get("end_date"),
                )
            )
        except InvalidDashboardQuery as error:
            raise ValidationError({"detail": str(error)}) from error

        return Response(
            {
                "period": result.period.value,
                "start_date": result.start_date,
                "end_date": result.end_date,
                "summary_count": len(result.summaries),
                "is_empty": not result.summaries,
                "has_stale_data": result.has_stale_data,
                "summaries": DashboardSummarySerializer(
                    result.summaries,
                    many=True,
                ).data,
            }
        )


def _authenticated_user_id(request: Request) -> UUID:
    user_id = request.user.pk
    if not isinstance(user_id, UUID):
        raise ValidationError({"detail": "Authenticated identity is invalid."})
    return user_id
