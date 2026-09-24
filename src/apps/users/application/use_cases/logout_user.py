"""User logout use case."""

from apps.users.application.ports.security import UserSession


class LogoutUser:
    """End the current user session."""

    def __init__(self, session: UserSession) -> None:
        self._session = session

    def execute(self) -> None:
        self._session.logout()
