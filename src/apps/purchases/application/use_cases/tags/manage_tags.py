"""Tag catalogue use cases."""

from apps.purchases.application.commands import (
    CreateTagCommand,
    ListTagsCommand,
)
from apps.purchases.application.dto import TagDetails, tag_details, tag_details_list
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.ports.repositories import TagRepository
from apps.purchases.domain.exceptions import PurchasesDomainError


class ListTags:
    """Return the whole tag catalogue, ordered by name."""

    def __init__(self, tags: TagRepository) -> None:
        self._tags = tags

    def execute(self, command: ListTagsCommand) -> list[TagDetails]:
        return tag_details_list(self._tags.list_all())


class CreateTag:
    """Add a tag to the catalogue, or return the existing one with that name.

    Idempotent on purpose: tagging the same concept twice should not create a
    second catalogue entry that the owner has to clean up later.
    """

    def __init__(self, tags: TagRepository) -> None:
        self._tags = tags

    def execute(self, command: CreateTagCommand) -> TagDetails:
        name = command.name.strip()
        if not name:
            raise InvalidPurchasesInput("Tag name cannot be empty.")
        try:
            return tag_details(self._tags.get_or_create(name))
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
