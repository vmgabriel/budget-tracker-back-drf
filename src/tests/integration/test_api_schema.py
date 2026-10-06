"""OpenAPI schema and Swagger UI smoke tests."""

import pytest
from django.test import Client


@pytest.mark.integration
def test_openapi_schema_is_served() -> None:
    response = Client().get("/api/schema/?format=json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/users/auth/login/" in schema["paths"]
    assert "/api/v1/users/auth/refresh/" in schema["paths"]
    assert "/api/v1/users/me/" in schema["paths"]
    assert "/api/v1/auth/login/" not in schema["paths"]
    assert "/api/v1/transactions/" in schema["paths"]
    assert "/api/v1/dashboard/overview/" in schema["paths"]
    assert "/api/v1/tasks/tasks/" in schema["paths"]
    assert "/api/v1/tasks/tasks/{id}/mark-done/" in schema["paths"]
    assert "/api/v1/tasks/goals/{id}/link-task/" in schema["paths"]
    assert "/api/v1/tasks/daily-plans/{id}/add-task/" in schema["paths"]
    assert "Bearer" in schema["components"]["securitySchemes"]
    assert schema["components"]["securitySchemes"]["Bearer"]["scheme"] == "bearer"
    transaction_parameters = {
        parameter["name"]
        for parameter in schema["paths"]["/api/v1/transactions/"]["get"].get(
            "parameters", []
        )
    }
    assert {"page", "page_size"}.issubset(transaction_parameters)
    dashboard_parameters = {
        parameter["name"]
        for parameter in schema["paths"]["/api/v1/dashboard/"]["get"].get(
            "parameters", []
        )
    }
    assert {"period", "start_date", "end_date"}.issubset(dashboard_parameters)
    assert "ErrorResponse" in schema["components"]["schemas"]


@pytest.mark.integration
def test_swagger_ui_is_served() -> None:
    response = Client().get("/api/schema/swagger-ui/")

    assert response.status_code == 200
    assert b"swagger" in response.content.lower()
