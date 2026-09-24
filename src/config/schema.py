"""OpenAPI extensions for the project's session authentication flow."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAuthenticationScheme(OpenApiAuthenticationExtension):
    """Describe the session cookie and CSRF header used by the API."""

    target_class = "rest_framework.authentication.SessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        """Return the OpenAPI security definition for session clients."""
        del auto_schema
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "sessionid",
            "description": (
                "Django session cookie. Authenticated unsafe requests also "
                "require the csrftoken cookie value in X-CSRFToken."
            ),
        }
