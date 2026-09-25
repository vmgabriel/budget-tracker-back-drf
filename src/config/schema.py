"""OpenAPI extensions for the JWT authentication flow."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Describe the bearer token accepted by the API."""

    target_class = "rest_framework_simplejwt.authentication.JWTAuthentication"
    name = "Bearer"
    priority = 1

    def get_security_requirement(self, auto_schema: object) -> Any:
        """Use the project-wide Bearer security setting for protected routes."""
        del auto_schema
        return None

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        """Return the OpenAPI HTTP bearer security definition."""
        del auto_schema
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
