"""Document listing use case."""

from uuid import UUID

from apps.rentals.application.dto import DocumentDetails, document_details
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    DocumentRepository,
    HouseRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.value_objects import ApartmentId


class ListApartmentDocuments:
    """Return every document of an apartment owned by the requesting user."""

    def __init__(
        self,
        documents: DocumentRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
    ) -> None:
        self._documents = documents
        self._apartments = apartments
        self._houses = houses

    def execute(self, apartment_id: UUID, owner_id: UUID) -> list[DocumentDetails]:
        require_apartment_for_owner(
            self._apartments, self._houses, ApartmentId(apartment_id), owner_id
        )
        documents = self._documents.get_by_apartment_id(ApartmentId(apartment_id))
        return [document_details(document) for document in documents]
