"""URL routes for the transactions bounded context."""

from django.urls import path

from apps.transactions.interfaces.views import (
    AccountDetailView,
    AccountListCreateView,
    TransactionAnalyticsView,
    TransactionDetailView,
    TransactionListCreateView,
)

app_name = "transactions"

urlpatterns = [
    path(
        "",
        TransactionListCreateView.as_view(),
        name="list",
    ),
    path(
        "analytics/",
        TransactionAnalyticsView.as_view(),
        name="analytics",
    ),
    path(
        "accounts/",
        AccountListCreateView.as_view(),
        name="account-list",
    ),
    path(
        "accounts/<uuid:account_id>/",
        AccountDetailView.as_view(),
        name="account-detail",
    ),
    path(
        "<uuid:transaction_id>/",
        TransactionDetailView.as_view(),
        name="detail",
    ),
]
