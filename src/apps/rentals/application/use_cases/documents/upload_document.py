"""Document upload use case."""

from dataclasses import dataclass
from uuid import UUID

from apps.rentals.application.dto import DocumentDetails, document_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    DocumentRepository,
    HouseRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.entities import Document
from apps.rentals.domain.exceptions import RentalsDomainError
from apps.rentals.domain.value_objects import ApartmentId, DocumentType
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UploadDocumentCommand:
    """Input required to attach a document to an apartment."""

    apartment_id: UUID
    owner_id: UUID
    document_type: str
    file_url: str
    description: str | None = None


class UploadDocument:
    """Attach a document to an apartment owned by the requesting user."""

    def __init__(
        self,
        documents: DocumentRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
        clock: Clock,
    ) -> None:
        self._documents = documents
        self._apartments = apartments
        self._houses = houses
        self._clock = clock

    def execute(self, command: UploadDocumentCommand) -> DocumentDetails:
        require_apartment_for_owner(
            self._apartments,
            self._houses,
            ApartmentId(command.apartment_id),
            command.owner_id,
        )
        try:
            document_type = DocumentType(command.document_type)
        except ValueError as error:
            raise InvalidRentalsInput(str(error)) from error
        try:
            document = Document.create(
                apartment_id=ApartmentId(command.apartment_id),
                document_type=document_type,
                file_url=command.file_url,
                description=command.description,
                now=self._clock.now(),
            )
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return document_details(self._documents.save(document))
