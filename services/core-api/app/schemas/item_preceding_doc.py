import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ItemPrecedingDocCreate(BaseModel):
    doc_kind_code: Optional[str] = None
    doc_name: Optional[str] = None
    customs_office_code: Optional[str] = None
    doc_date: Optional[date] = None
    customs_doc_number: Optional[str] = None
    other_doc_number: Optional[str] = None
    other_doc_date: Optional[date] = None
    goods_number: Optional[int] = None
    line_id: Optional[str] = None
    sort_order: int = 0


class ItemPrecedingDocUpdate(BaseModel):
    doc_kind_code: Optional[str] = None
    doc_name: Optional[str] = None
    customs_office_code: Optional[str] = None
    doc_date: Optional[date] = None
    customs_doc_number: Optional[str] = None
    other_doc_number: Optional[str] = None
    other_doc_date: Optional[date] = None
    goods_number: Optional[int] = None
    line_id: Optional[str] = None
    sort_order: Optional[int] = None


class ItemPrecedingDocResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    declaration_item_id: uuid.UUID
    doc_kind_code: Optional[str] = None
    doc_name: Optional[str] = None
    customs_office_code: Optional[str] = None
    doc_date: Optional[date] = None
    customs_doc_number: Optional[str] = None
    other_doc_number: Optional[str] = None
    other_doc_date: Optional[date] = None
    goods_number: Optional[int] = None
    line_id: Optional[str] = None
    sort_order: int
    created_at: Optional[datetime] = None
