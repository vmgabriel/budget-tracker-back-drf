"""DRF permissions enforcing account ban status."""

from typing import Any

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class IsNotBanned(BasePermission):
    """Reject requests from users whose account has been banned."""

    def has_permission(self, request: Request, view: Any) -> bool:
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return True  # IsAuthenticated handles anonymity; defense in depth.
        if getattr(request.user, "is_banned", False):
            raise PermissionDenied(
                detail={
                    "error": {
                        "code": "account_banned",
                        "message": "Your account has been suspended.",
                        "details": {"reason": request.user.ban_reason},
                    }
                }
            )
        return True
