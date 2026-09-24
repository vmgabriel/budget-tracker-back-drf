"""Tests for the shared DRF error envelope."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.integration
@pytest.mark.django_db
def test_validation_errors_include_stable_error_metadata() -> None:
    response = APIClient().post(
        reverse("api_v1:users:register"),
        {
            "email": "not-an-email",
            "full_name": "Example User",
            "password": "StrongPassword123!",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert "email" in response.data["error"]["details"]
    assert response.data["detail"] == "The request contains invalid data."
    # Keep the legacy top-level field while clients migrate to the envelope.
    assert "email" in response.data
