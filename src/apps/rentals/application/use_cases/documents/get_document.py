"""Single document query use case."""

from uuid import UUID

from apps.rentals.application.dto import DocumentDetails, document_details
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    DocumentRepository,
    HouseRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.exceptions import ApartmentNotFound, DocumentNotFound
from apps.rentals.domain.value_objects import DocumentId


class GetDocument:
    """Return a document only when its apartment belongs to the user."""

    def __init__(
        self,
        documents: DocumentRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
    ) -> None:
        self._documents = documents
        self._apartments = apartments
        self._houses = houses

    def execute(self, document_id: UUID, owner_id: UUID) -> DocumentDetails:
        document = self._documents.get_by_id(DocumentId(document_id))
        if document is None:
            raise DocumentNotFound("Document not found.")
        try:
            require_apartment_for_owner(
                self._apartments, self._houses, document.apartment_id, owner_id
            )
        except ApartmentNotFound as error:
            raise DocumentNotFound("Document not found.") from error
        return document_details(document)
