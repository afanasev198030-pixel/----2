import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DeclarationItemCreate(BaseModel):
    item_no: int
    description: Optional[str] = None
    package_count: Optional[int] = None
    package_type: Optional[str] = None
    commercial_name: Optional[str] = None
    manufacturer: Optional[str] = None
    trademark: Optional[str] = None
    model_name: Optional[str] = None
    article_number: Optional[str] = None
    hs_code: Optional[str] = None
    hs_code_letters: Optional[str] = None
    hs_code_extra: Optional[str] = None
    country_origin_code: Optional[str] = None
    country_origin_pref_code: Optional[str] = None
    gross_weight: Optional[Decimal] = None
    preference_code: Optional[str] = None
    procedure_code: Optional[str] = None
    net_weight: Optional[Decimal] = None
    quota_info: Optional[str] = None
    prev_doc_ref: Optional[str] = None
    additional_unit: Optional[str] = None
    additional_unit_qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    mos_method_code: Optional[str] = None
    customs_value_rub: Optional[Decimal] = None
    statistical_value_usd: Optional[Decimal] = None
    documents_json: Optional[list] = None
    package_type_code: Optional[str] = None
    package_marks: Optional[str] = None
    additional_unit_code: Optional[str] = None


class DeclarationItemUpdate(BaseModel):
    item_no: Optional[int] = None
    description: Optional[str] = None
    package_count: Optional[int] = None
    package_type: Optional[str] = None
    commercial_name: Optional[str] = None
    manufacturer: Optional[str] = None
    trademark: Optional[str] = None
    model_name: Optional[str] = None
    article_number: Optional[str] = None
    hs_code: Optional[str] = None
    hs_code_letters: Optional[str] = None
    hs_code_extra: Optional[str] = None
    country_origin_code: Optional[str] = None
    country_origin_pref_code: Optional[str] = None
    gross_weight: Optional[Decimal] = None
    preference_code: Optional[str] = None
    procedure_code: Optional[str] = None
    net_weight: Optional[Decimal] = None
    quota_info: Optional[str] = None
    prev_doc_ref: Optional[str] = None
    additional_unit: Optional[str] = None
    additional_unit_qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    mos_method_code: Optional[str] = None
    customs_value_rub: Optional[Decimal] = None
    statistical_value_usd: Optional[Decimal] = None
    documents_json: Optional[list] = None
    package_type_code: Optional[str] = None
    package_marks: Optional[str] = None
    additional_unit_code: Optional[str] = None


class DeclarationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    declaration_id: uuid.UUID
    item_no: Optional[int]
    description: Optional[str]
    package_count: Optional[int]
    package_type: Optional[str]
    commercial_name: Optional[str]
    manufacturer: Optional[str] = None
    trademark: Optional[str] = None
    model_name: Optional[str] = None
    article_number: Optional[str] = None
    hs_code: Optional[str]
    hs_code_letters: Optional[str] = None
    hs_code_extra: Optional[str] = None
    country_origin_code: Optional[str]
    country_origin_pref_code: Optional[str] = None
    gross_weight: Optional[Decimal]
    preference_code: Optional[str]
    procedure_code: Optional[str]
    net_weight: Optional[Decimal]
    quota_info: Optional[str]
    prev_doc_ref: Optional[str]
    additional_unit: Optional[str]
    additional_unit_qty: Optional[Decimal]
    unit_price: Optional[Decimal]
    mos_method_code: Optional[str]
    customs_value_rub: Optional[Decimal]
    statistical_value_usd: Optional[Decimal] = None
    documents_json: Optional[list] = None
    package_type_code: Optional[str] = None
    package_marks: Optional[str] = None
    additional_unit_code: Optional[str] = None
    risk_score: int
    risk_flags: Optional[dict]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
