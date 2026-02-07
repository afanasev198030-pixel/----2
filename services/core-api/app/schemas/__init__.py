from .auth import LoginRequest, TokenResponse, RegisterRequest
from .user import UserCreate, UserUpdate, UserResponse
from .company import CompanyCreate, CompanyUpdate, CompanyResponse
from .counterparty import CounterpartyCreate, CounterpartyUpdate, CounterpartyResponse
from .declaration import (
    DeclarationCreate,
    DeclarationUpdate,
    DeclarationResponse,
    DeclarationListResponse,
    StatusChangeRequest,
)
from .declaration_item import (
    DeclarationItemCreate,
    DeclarationItemUpdate,
    DeclarationItemResponse,
)
from .document import DocumentCreate, DocumentUpdate, DocumentResponse
from .classifier import ClassifierResponse
from .common import PaginatedResponse, MessageResponse

__all__ = [
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RegisterRequest",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    # Company
    "CompanyCreate",
    "CompanyUpdate",
    "CompanyResponse",
    # Counterparty
    "CounterpartyCreate",
    "CounterpartyUpdate",
    "CounterpartyResponse",
    # Declaration
    "DeclarationCreate",
    "DeclarationUpdate",
    "DeclarationResponse",
    "DeclarationListResponse",
    "StatusChangeRequest",
    # Declaration Item
    "DeclarationItemCreate",
    "DeclarationItemUpdate",
    "DeclarationItemResponse",
    # Document
    "DocumentCreate",
    "DocumentUpdate",
    "DocumentResponse",
    # Classifier
    "ClassifierResponse",
    # Common
    "PaginatedResponse",
    "MessageResponse",
]
