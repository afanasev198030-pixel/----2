import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ItemDocumentCreate(BaseModel):
    doc_kind_code: str
    doc_number: Optional[str] = None
    doc_date: Optional[date] = None
    doc_validity_date: Optional[date] = None
    authority_name: Optional[str] = None
    country_code: Optional[str] = None
    edoc_code: Optional[str] = None
    archive_doc_id: Optional[str] = None
    line_id: Optional[str] = None
    presenting_kind_code: Optional[str] = None
    doc_name: Optional[str] = None
    record_id: Optional[str] = None
    electronic_doc_id: Optional[str] = None
    electronic_arch_id: Optional[str] = None
    document_mode_id: Optional[str] = None
    doc_begin_date: Optional[date] = None
    presenting_customs_code: Optional[str] = None
    presenting_reg_date: Optional[date] = None
    presenting_gtd_number: Optional[str] = None
    sort_order: int = 0


class ItemDocumentUpdate(BaseModel):
    doc_kind_code: Optional[str] = None
    doc_number: Optional[str] = None
    doc_date: Optional[date] = None
    doc_validity_date: Optional[date] = None
    authority_name: Optional[str] = None
    country_code: Optional[str] = None
    edoc_code: Optional[str] = None
    archive_doc_id: Optional[str] = None
    line_id: Optional[str] = None
    presenting_kind_code: Optional[str] = None
    doc_name: Optional[str] = None
    record_id: Optional[str] = None
    electronic_doc_id: Optional[str] = None
    electronic_arch_id: Optional[str] = None
    document_mode_id: Optional[str] = None
    doc_begin_date: Optional[date] = None
    presenting_customs_code: Optional[str] = None
    presenting_reg_date: Optional[date] = None
    presenting_gtd_number: Optional[str] = None
    sort_order: Optional[int] = None


class ItemDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    declaration_item_id: uuid.UUID
    doc_kind_code: str
    doc_number: Optional[str] = None
    doc_date: Optional[date] = None
    doc_validity_date: Optional[date] = None
    authority_name: Optional[str] = None
    country_code: Optional[str] = None
    edoc_code: Optional[str] = None
    archive_doc_id: Optional[str] = None
    line_id: Optional[str] = None
    presenting_kind_code: Optional[str] = None
    doc_name: Optional[str] = None
    record_id: Optional[str] = None
    electronic_doc_id: Optional[str] = None
    electronic_arch_id: Optional[str] = None
    document_mode_id: Optional[str] = None
    doc_begin_date: Optional[date] = None
    presenting_customs_code: Optional[str] = None
    presenting_reg_date: Optional[date] = None
    presenting_gtd_number: Optional[str] = None
    sort_order: int
    created_at: Optional[datetime] = None
