"""Document use cases."""

from apps.rentals.application.use_cases.documents.delete_document import (
    DeleteDocument,
)
from apps.rentals.application.use_cases.documents.get_document import GetDocument
from apps.rentals.application.use_cases.documents.list_apartment_documents import (
    ListApartmentDocuments,
)
from apps.rentals.application.use_cases.documents.upload_document import (
    UploadDocument,
    UploadDocumentCommand,
)

__all__ = (
    "DeleteDocument",
    "GetDocument",
    "ListApartmentDocuments",
    "UploadDocument",
    "UploadDocumentCommand",
)
