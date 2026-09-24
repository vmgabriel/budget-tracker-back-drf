"""Smoke tests for the framework health endpoint."""

import pytest
from django.test import Client


@pytest.mark.integration
@pytest.mark.django_db
def test_health_reports_database_availability(client: Client) -> None:
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"database": "ok", "status": "ok"}


@pytest.mark.integration
def test_liveness_does_not_require_database(client: Client) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
