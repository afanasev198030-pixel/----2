import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

from .declaration_item import DeclarationItemResponse


class DeclarationCreate(BaseModel):
    type_code: str
    company_id: uuid.UUID
    number_internal: Optional[str] = None
    sender_counterparty_id: Optional[uuid.UUID] = None
    receiver_counterparty_id: Optional[uuid.UUID] = None
    financial_counterparty_id: Optional[uuid.UUID] = None
    declarant_counterparty_id: Optional[uuid.UUID] = None
    country_dispatch_code: Optional[str] = None
    country_origin_code: Optional[str] = None
    country_destination_code: Optional[str] = None
    transport_at_border: Optional[str] = None
    container_info: Optional[str] = None
    incoterms_code: Optional[str] = None
    transport_on_border: Optional[str] = None
    currency_code: Optional[str] = None
    total_invoice_value: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    deal_nature_code: Optional[str] = None
    transport_type_border: Optional[str] = None
    transport_type_inland: Optional[str] = None
    loading_place: Optional[str] = None
    financial_info: Optional[str] = None
    total_customs_value: Optional[Decimal] = None
    total_gross_weight: Optional[Decimal] = None
    total_net_weight: Optional[Decimal] = None
    total_items_count: Optional[int] = None
    total_packages_count: Optional[int] = None
    forms_count: Optional[int] = None
    specifications_count: Optional[int] = None
    customs_office_code: Optional[str] = None
    warehouse_name: Optional[str] = None
    place_and_date: Optional[str] = None


class DeclarationUpdate(BaseModel):
    number_internal: Optional[str] = None
    type_code: Optional[str] = None
    sender_counterparty_id: Optional[uuid.UUID] = None
    receiver_counterparty_id: Optional[uuid.UUID] = None
    financial_counterparty_id: Optional[uuid.UUID] = None
    declarant_counterparty_id: Optional[uuid.UUID] = None
    country_dispatch_code: Optional[str] = None
    country_origin_code: Optional[str] = None
    country_destination_code: Optional[str] = None
    transport_at_border: Optional[str] = None
    container_info: Optional[str] = None
    incoterms_code: Optional[str] = None
    transport_on_border: Optional[str] = None
    currency_code: Optional[str] = None
    total_invoice_value: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    deal_nature_code: Optional[str] = None
    transport_type_border: Optional[str] = None
    transport_type_inland: Optional[str] = None
    loading_place: Optional[str] = None
    financial_info: Optional[str] = None
    total_customs_value: Optional[Decimal] = None
    total_gross_weight: Optional[Decimal] = None
    total_net_weight: Optional[Decimal] = None
    total_items_count: Optional[int] = None
    total_packages_count: Optional[int] = None
    forms_count: Optional[int] = None
    specifications_count: Optional[int] = None
    customs_office_code: Optional[str] = None
    warehouse_name: Optional[str] = None
    place_and_date: Optional[str] = None


class DeclarationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number_internal: Optional[str]
    type_code: Optional[str]
    status: str
    company_id: uuid.UUID
    sender_counterparty_id: Optional[uuid.UUID]
    receiver_counterparty_id: Optional[uuid.UUID]
    financial_counterparty_id: Optional[uuid.UUID]
    declarant_counterparty_id: Optional[uuid.UUID]
    country_dispatch_code: Optional[str]
    country_origin_code: Optional[str]
    country_destination_code: Optional[str]
    transport_at_border: Optional[str]
    container_info: Optional[str]
    incoterms_code: Optional[str]
    transport_on_border: Optional[str]
    currency_code: Optional[str]
    total_invoice_value: Optional[Decimal]
    exchange_rate: Optional[Decimal]
    deal_nature_code: Optional[str]
    transport_type_border: Optional[str]
    transport_type_inland: Optional[str]
    loading_place: Optional[str]
    financial_info: Optional[str]
    total_customs_value: Optional[Decimal]
    total_gross_weight: Optional[Decimal]
    total_net_weight: Optional[Decimal]
    total_items_count: Optional[int]
    total_packages_count: Optional[int]
    forms_count: Optional[int]
    specifications_count: Optional[int]
    customs_office_code: Optional[str]
    warehouse_name: Optional[str]
    spot_required: bool
    spot_status: str
    spot_qr_file_key: Optional[str]
    spot_amount: Optional[Decimal]
    submitted_at: Optional[datetime]
    place_and_date: Optional[str]
    created_by: uuid.UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    items: list[DeclarationItemResponse] = []


class DeclarationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number_internal: Optional[str]
    type_code: Optional[str]
    status: str
    company_id: uuid.UUID
    total_invoice_value: Optional[Decimal]
    currency_code: Optional[str]
    total_items_count: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class StatusChangeRequest(BaseModel):
    new_status: str
