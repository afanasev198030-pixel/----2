from .auth import LoginRequest, TokenResponse, RegisterRequest, PublicRegisterRequest
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
from .broker_client import BrokerClientCreate, BrokerClientUpdate, BrokerClientResponse
from .item_document import ItemDocumentCreate, ItemDocumentUpdate, ItemDocumentResponse
from .item_preceding_doc import ItemPrecedingDocCreate, ItemPrecedingDocUpdate, ItemPrecedingDocResponse
from .customs_value_declaration import (
    CustomsValueDeclarationUpdate,
    CustomsValueDeclarationResponse,
    CustomsValueItemCreate,
    CustomsValueItemUpdate,
    CustomsValueItemResponse,
)
from .common import PaginatedResponse, MessageResponse

__all__ = [
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RegisterRequest",
    "PublicRegisterRequest",
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
    # Broker Client
    "BrokerClientCreate",
    "BrokerClientUpdate",
    "BrokerClientResponse",
    # Item Documents (графа 44)
    "ItemDocumentCreate",
    "ItemDocumentUpdate",
    "ItemDocumentResponse",
    # Item Preceding Docs (графа 40)
    "ItemPrecedingDocCreate",
    "ItemPrecedingDocUpdate",
    "ItemPrecedingDocResponse",
    # Customs Value Declaration (ДТС)
    "CustomsValueDeclarationUpdate",
    "CustomsValueDeclarationResponse",
    "CustomsValueItemCreate",
    "CustomsValueItemUpdate",
    "CustomsValueItemResponse",
    # Common
    "PaginatedResponse",
    "MessageResponse",
]
