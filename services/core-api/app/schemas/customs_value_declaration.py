import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CustomsValueItemCreate(BaseModel):
    declaration_item_id: uuid.UUID
    item_no: int
    hs_code: Optional[str] = None
    invoice_price_foreign: Optional[Decimal] = None
    invoice_price_national: Optional[Decimal] = None
    indirect_payments: Optional[Decimal] = 0
    broker_commission: Optional[Decimal] = 0
    packaging_cost: Optional[Decimal] = 0
    raw_materials: Optional[Decimal] = 0
    tools_molds: Optional[Decimal] = 0
    consumed_materials: Optional[Decimal] = 0
    design_engineering: Optional[Decimal] = 0
    license_payments: Optional[Decimal] = 0
    seller_income: Optional[Decimal] = 0
    transport_cost: Optional[Decimal] = 0
    loading_unloading: Optional[Decimal] = 0
    insurance_cost: Optional[Decimal] = 0
    construction_after_import: Optional[Decimal] = 0
    inland_transport: Optional[Decimal] = 0
    duties_taxes: Optional[Decimal] = 0


class CustomsValueItemUpdate(BaseModel):
    invoice_price_foreign: Optional[Decimal] = None
    invoice_price_national: Optional[Decimal] = None
    indirect_payments: Optional[Decimal] = None
    broker_commission: Optional[Decimal] = None
    packaging_cost: Optional[Decimal] = None
    raw_materials: Optional[Decimal] = None
    tools_molds: Optional[Decimal] = None
    consumed_materials: Optional[Decimal] = None
    design_engineering: Optional[Decimal] = None
    license_payments: Optional[Decimal] = None
    seller_income: Optional[Decimal] = None
    transport_cost: Optional[Decimal] = None
    loading_unloading: Optional[Decimal] = None
    insurance_cost: Optional[Decimal] = None
    construction_after_import: Optional[Decimal] = None
    inland_transport: Optional[Decimal] = None
    duties_taxes: Optional[Decimal] = None
    currency_conversions: Optional[list] = None


class CustomsValueItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customs_value_declaration_id: uuid.UUID
    declaration_item_id: uuid.UUID
    item_no: int
    hs_code: Optional[str] = None
    invoice_price_foreign: Optional[Decimal] = None
    invoice_price_national: Optional[Decimal] = None
    indirect_payments: Optional[Decimal] = None
    base_total: Optional[Decimal] = None
    broker_commission: Optional[Decimal] = None
    packaging_cost: Optional[Decimal] = None
    raw_materials: Optional[Decimal] = None
    tools_molds: Optional[Decimal] = None
    consumed_materials: Optional[Decimal] = None
    design_engineering: Optional[Decimal] = None
    license_payments: Optional[Decimal] = None
    seller_income: Optional[Decimal] = None
    transport_cost: Optional[Decimal] = None
    loading_unloading: Optional[Decimal] = None
    insurance_cost: Optional[Decimal] = None
    additions_total: Optional[Decimal] = None
    construction_after_import: Optional[Decimal] = None
    inland_transport: Optional[Decimal] = None
    duties_taxes: Optional[Decimal] = None
    deductions_total: Optional[Decimal] = None
    customs_value_national: Optional[Decimal] = None
    customs_value_usd: Optional[Decimal] = None
    currency_conversions: Optional[list] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomsValueDeclarationUpdate(BaseModel):
    related_parties: Optional[bool] = None
    transport_carrier_name: Optional[str] = None
    transport_destination: Optional[str] = None
    related_price_impact: Optional[bool] = None
    related_verification: Optional[bool] = None
    restrictions: Optional[bool] = None
    price_conditions: Optional[bool] = None
    ip_license_payments: Optional[bool] = None
    sale_depends_on_income: Optional[bool] = None
    income_to_seller: Optional[bool] = None
    additional_docs: Optional[str] = None
    additional_data: Optional[str] = None
    filler_name: Optional[str] = None
    filler_date: Optional[date] = None
    filler_document: Optional[str] = None
    filler_contacts: Optional[str] = None
    filler_position: Optional[str] = None


class CustomsValueDeclarationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    declaration_id: uuid.UUID
    form_type: str
    related_parties: bool
    related_price_impact: bool
    related_verification: bool
    restrictions: bool
    price_conditions: bool
    ip_license_payments: bool
    sale_depends_on_income: bool
    income_to_seller: bool
    additional_docs: Optional[str] = None
    additional_data: Optional[str] = None
    filler_name: Optional[str] = None
    filler_date: Optional[date] = None
    filler_document: Optional[str] = None
    filler_contacts: Optional[str] = None
    filler_position: Optional[str] = None
    transport_carrier_name: Optional[str] = None
    transport_destination: Optional[str] = None
    usd_exchange_rate: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: list[CustomsValueItemResponse] = []
