"""URL routes for the transactions bounded context."""

from django.urls import path

from apps.transactions.interfaces.views import (
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
        "<uuid:transaction_id>/",
        TransactionDetailView.as_view(),
        name="detail",
    ),
]
