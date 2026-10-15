"""Security posture integration tests: throttling, CORS, and response headers."""

from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from shared.infrastructure.throttling import (
    LoginRateThrottle,
    RegisterRateThrottle,
)
from tests.factories import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _login_payload(email: str = "throttle@example.com") -> dict[str, str]:
    return {"email": email, "password": "securepass123"}


class TestLoginThrottle:
    """The login budget must exist, and must key on the client address."""

    def test_repeated_failures_are_throttled_with_the_standard_envelope(self) -> None:
        UserFactory(email="throttle@example.com", password="securepass123")
        client = APIClient()
        url = reverse("api_v1:users:login")
        wrong_password = {"email": "throttle@example.com", "password": "wrong-password"}

        for _ in range(10):
            response = client.post(url, wrong_password, format="json")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        throttled = client.post(url, wrong_password, format="json")

        assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert throttled.data["error"]["code"] == "throttled"
        assert throttled["Retry-After"] == "60"

    def test_a_throttled_client_cannot_get_a_token_even_with_valid_credentials(
        self,
    ) -> None:
        UserFactory(email="throttle@example.com", password="securepass123")
        client = APIClient()
        url = reverse("api_v1:users:login")

        for _ in range(10):
            client.post(url, {"email": "throttle@example.com", "password": "wrong"})
        response = client.post(url, _login_payload(), format="json")

        # Correct password, but the budget is spent: a throttle must not leak a
        # token to a caller who just waited out the limit.
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "access" not in response.data

    def test_a_successful_login_also_consumes_the_budget(self) -> None:
        UserFactory(email="throttle@example.com", password="securepass123")
        client = APIClient()
        url = reverse("api_v1:users:login")

        for _ in range(10):
            response = client.post(url, _login_payload(), format="json")
            assert response.status_code == status.HTTP_200_OK

        assert (
            client.post(url, _login_payload(), format="json").status_code
            == status.HTTP_429_TOO_MANY_REQUESTS
        )

    def test_another_client_is_unaffected(self) -> None:
        UserFactory(email="throttle@example.com", password="securepass123")
        url = reverse("api_v1:users:login")

        noisy = APIClient(REMOTE_ADDR="198.51.100.10")
        for _ in range(11):
            noisy.post(url, _login_payload(), format="json")

        quiet = APIClient(REMOTE_ADDR="198.51.100.99")
        response = quiet.post(url, _login_payload(), format="json")

        assert response.status_code == status.HTTP_200_OK

    def test_the_view_declares_the_login_throttle(self) -> None:
        assert LoginRateThrottle in self._login_view_throttles()

    def test_the_view_declares_the_register_throttle(self) -> None:
        assert RegisterRateThrottle in self._register_view_throttles()

    @staticmethod
    def _login_view_throttles() -> tuple[type, ...]:
        from apps.users.interfaces.views import CustomTokenObtainPairView

        return tuple(CustomTokenObtainPairView.throttle_classes)

    @staticmethod
    def _register_view_throttles() -> tuple[type, ...]:
        from apps.users.interfaces.views import RegisterView

        return tuple(RegisterView.throttle_classes)


class TestRegisterThrottle:
    def test_account_creation_is_capped(self) -> None:
        client = APIClient()
        url = reverse("api_v1:users:register")

        for index in range(5):
            response = client.post(
                url,
                {
                    "email": f"new-owner-{index}@example.com",
                    "password": "securepass123",
                    "full_name": f"Owner {index}",
                },
                format="json",
            )
            assert response.status_code == status.HTTP_201_CREATED

        blocked = client.post(
            url,
            {
                "email": "new-owner-5@example.com",
                "password": "securepass123",
                "full_name": "Owner 5",
            },
            format="json",
        )

        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert blocked.data["error"]["code"] == "throttled"
        assert blocked["Retry-After"] == "3600"

    def test_a_blocked_registration_creates_no_user(
        self, django_user_model: Any
    ) -> None:
        client = APIClient()
        url = reverse("api_v1:users:register")

        for index in range(6):
            client.post(
                url,
                {
                    "email": f"new-owner-{index}@example.com",
                    "password": "securepass123",
                    "full_name": f"Owner {index}",
                },
                format="json",
            )

        blocked = client.post(
            url,
            {
                "email": "new-owner-blocked@example.com",
                "password": "securepass123",
                "full_name": "Owner Blocked",
            },
            format="json",
        )

        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        # A rejected request must leave no trace: no half-created user, and no
        # provisioning signal sent on their behalf.
        assert not django_user_model.objects.filter(
            email="new-owner-blocked@example.com"
        ).exists()


class TestSecurityHeaders:
    @pytest.mark.parametrize(
        "url_name",
        ["liveness", "api_v1:users:login"],
    )
    def test_hardening_headers_are_present(self, url_name: str) -> None:
        response = APIClient().get(reverse(url_name))

        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert response["Referrer-Policy"] in {
            "same-origin",
            "strict-origin-when-cross-origin",
        }
        assert "camera=()" in response["Permissions-Policy"]
        assert "geolocation=()" in response["Permissions-Policy"]

    def test_headers_are_present_on_error_responses_too(self) -> None:
        # An error path that skipped the middleware would leak the absence of
        # protection exactly when a client is least likely to notice.
        response = APIClient().get("/api/v1/does-not-exist/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response["X-Content-Type-Options"] == "nosniff"
        assert "camera=()" in response["Permissions-Policy"]


class TestCorsPolicy:
    def test_a_disallowed_origin_gets_no_cors_headers(self) -> None:
        response = APIClient().get(
            reverse("api_v1:users:current-user"), HTTP_ORIGIN="https://evil.example"
        )

        assert "Access-Control-Allow-Origin" not in response

    def test_an_allowlisted_origin_is_accepted(self, settings: Any) -> None:
        settings.CORS_ALLOWED_ORIGINS = ["https://bff.example.com"]

        response = APIClient().get(
            reverse("api_v1:users:current-user"),
            HTTP_ORIGIN="https://bff.example.com",
        )

        assert response["Access-Control-Allow-Origin"] == "https://bff.example.com"

    def test_credentials_are_never_allowed_even_for_an_allowlisted_origin(
        self, settings: Any
    ) -> None:
        # The BFF authenticates with a bearer token; permitting credentials
        # would let a browser attach ambient authority to a cross-origin call.
        settings.CORS_ALLOWED_ORIGINS = ["https://bff.example.com"]

        response = APIClient().get(
            reverse("api_v1:users:current-user"),
            HTTP_ORIGIN="https://bff.example.com",
        )

        assert "Access-Control-Allow-Credentials" not in response

    def test_preflight_is_answered_for_an_allowlisted_origin(
        self, settings: Any
    ) -> None:
        settings.CORS_ALLOWED_ORIGINS = ["https://bff.example.com"]

        response = APIClient().options(
            reverse("api_v1:users:login"),
            HTTP_ORIGIN="https://bff.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Access-Control-Allow-Origin"] == "https://bff.example.com"
        assert "POST" in response["Access-Control-Allow-Methods"]
        # django-cors-headers echoes the allowed headers lowercased.
        assert "authorization" in response["Access-Control-Allow-Headers"].lower()

    def test_preflight_from_an_unknown_origin_is_not_approved(
        self, settings: Any
    ) -> None:
        settings.CORS_ALLOWED_ORIGINS = ["https://bff.example.com"]

        response = APIClient().options(
            reverse("api_v1:users:login"),
            HTTP_ORIGIN="https://evil.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )

        assert "Access-Control-Allow-Origin" not in response
