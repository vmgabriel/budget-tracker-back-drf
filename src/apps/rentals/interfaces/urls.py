"""URL routes for the rentals bounded context."""

from django.urls import path

from apps.rentals.interfaces.views import (
    ApartmentDetailView,
    ApartmentListView,
    DocumentDetailView,
    DocumentListView,
    HouseDetailView,
    HouseListView,
    PaymentRecordDetailView,
    PaymentRecordListView,
    PaymentSummaryView,
    UtilityBillView,
    UtilityReadingDetailView,
    UtilityReadingListView,
)

app_name = "rentals"

urlpatterns = [
    # Houses
    path("houses/", HouseListView.as_view(), name="house-list"),
    path("houses/<uuid:pk>/", HouseDetailView.as_view(), name="house-detail"),
    # Apartments
    path("apartments/", ApartmentListView.as_view(), name="apartment-list"),
    path(
        "apartments/<uuid:pk>/", ApartmentDetailView.as_view(), name="apartment-detail"
    ),
    # Documents (nested under apartments)
    path(
        "apartments/<uuid:apartment_id>/documents/",
        DocumentListView.as_view(),
        name="document-list",
    ),
    path("documents/<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    # Utilities (nested under apartments)
    path(
        "apartments/<uuid:apartment_id>/utilities/",
        UtilityReadingListView.as_view(),
        name="utility-reading-list",
    ),
    path(
        "utilities/<uuid:pk>/",
        UtilityReadingDetailView.as_view(),
        name="utility-reading-detail",
    ),
    path(
        "apartments/<uuid:apartment_id>/utilities/bill/",
        UtilityBillView.as_view(),
        name="utility-bill",
    ),
    # Payments (nested under apartments)
    path(
        "apartments/<uuid:apartment_id>/payments/",
        PaymentRecordListView.as_view(),
        name="payment-list",
    ),
    path(
        "payments/<uuid:pk>/",
        PaymentRecordDetailView.as_view(),
        name="payment-detail",
    ),
    path(
        "apartments/<uuid:apartment_id>/payments/summary/",
        PaymentSummaryView.as_view(),
        name="payment-summary",
    ),
]
