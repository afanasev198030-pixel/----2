import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    declaration_id: Optional[uuid.UUID] = None
    item_id: Optional[uuid.UUID] = None
    doc_type: str
    file_key: str
    original_filename: str
    mime_type: str
    file_size: int
    issued_at: Optional[date] = None
    issuer: Optional[str] = None
    doc_number: Optional[str] = None
    linked_fields: Optional[list[str]] = None


class DocumentUpdate(BaseModel):
    doc_type: Optional[str] = None
    issued_at: Optional[date] = None
    issuer: Optional[str] = None
    doc_number: Optional[str] = None
    linked_fields: Optional[list[str]] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    declaration_id: Optional[uuid.UUID]
    item_id: Optional[uuid.UUID]
    doc_type: str
    file_key: Optional[str]
    original_filename: Optional[str]
    mime_type: Optional[str]
    file_size: Optional[int]
    issued_at: Optional[date]
    issuer: Optional[str]
    doc_number: Optional[str]
    parsed_data: Optional[dict]
    linked_fields: Optional[dict]
    created_at: Optional[datetime]
