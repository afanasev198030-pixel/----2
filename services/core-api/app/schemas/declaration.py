import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
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
    special_ref_code: Optional[str] = None
    country_dispatch_code: Optional[str] = None
    country_origin_name: Optional[str] = None
    country_destination_code: Optional[str] = None
    transport_at_border: Optional[str] = None
    container_info: Optional[str] = None
    incoterms_code: Optional[str] = None
    transport_on_border: Optional[str] = None
    currency_code: Optional[str] = None
    total_invoice_value: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    deal_nature_code: Optional[str] = None
    deal_specifics_code: Optional[str] = None
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
    trading_country_code: Optional[str] = None
    declarant_inn_kpp: Optional[str] = None
    declarant_ogrn: Optional[str] = None
    declarant_phone: Optional[str] = None
    delivery_place: Optional[str] = None
    transport_on_border_id: Optional[str] = None
    entry_customs_code: Optional[str] = None
    goods_location: Optional[str] = None
    payment_deferral: Optional[str] = None
    warehouse_requisites: Optional[str] = None
    transit_offices: Optional[str] = None
    destination_office_code: Optional[str] = None


class DeclarationUpdate(BaseModel):
    number_internal: Optional[str] = None
    type_code: Optional[str] = None
    sender_counterparty_id: Optional[uuid.UUID] = None
    receiver_counterparty_id: Optional[uuid.UUID] = None
    financial_counterparty_id: Optional[uuid.UUID] = None
    declarant_counterparty_id: Optional[uuid.UUID] = None
    special_ref_code: Optional[str] = None
    country_dispatch_code: Optional[str] = None
    country_origin_name: Optional[str] = None
    country_destination_code: Optional[str] = None
    transport_at_border: Optional[str] = None
    container_info: Optional[str] = None
    incoterms_code: Optional[str] = None
    transport_on_border: Optional[str] = None
    currency_code: Optional[str] = None
    total_invoice_value: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    deal_nature_code: Optional[str] = None
    deal_specifics_code: Optional[str] = None
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
    trading_country_code: Optional[str] = None
    declarant_inn_kpp: Optional[str] = None
    declarant_ogrn: Optional[str] = None
    declarant_phone: Optional[str] = None
    delivery_place: Optional[str] = None
    transport_on_border_id: Optional[str] = None
    entry_customs_code: Optional[str] = None
    goods_location: Optional[str] = None
    payment_deferral: Optional[str] = None
    warehouse_requisites: Optional[str] = None
    transit_offices: Optional[str] = None
    destination_office_code: Optional[str] = None
    country_first_destination_code: Optional[str] = None
    guarantee_info: Optional[str] = None
    freight_amount: Optional[Decimal] = None
    freight_currency: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_position: Optional[str] = None
    signatory_id_doc: Optional[str] = None
    signatory_cert_number: Optional[str] = None
    signatory_power_of_attorney: Optional[str] = None
    broker_registry_number: Optional[str] = None
    broker_contract_number: Optional[str] = None
    broker_contract_date: Optional[datetime] = None
    transport_reg_number: Optional[str] = None
    transport_nationality_code: Optional[str] = None
    goods_location_code: Optional[str] = None
    goods_location_customs_code: Optional[str] = None
    goods_location_zone_id: Optional[str] = None
    goods_location_info_type_code: Optional[str] = None
    goods_location_svh_doc_id: Optional[str] = None
    goods_location_address: Optional[str] = None
    border_customs_name: Optional[str] = None
    border_customs_country_code: Optional[str] = None
    transport_kind_code: Optional[str] = None
    transport_type_name: Optional[str] = None
    transport_means_quantity: Optional[int] = None
    signatory_surname: Optional[str] = None
    signatory_first_name: Optional[str] = None
    signatory_middle_name: Optional[str] = None
    signatory_phone: Optional[str] = None
    signatory_email: Optional[str] = None
    signatory_id_card_code: Optional[str] = None
    signatory_id_card_series: Optional[str] = None
    signatory_id_card_number: Optional[str] = None
    signatory_id_card_date: Optional[date] = None
    signatory_id_card_org: Optional[str] = None
    signatory_poa_number: Optional[str] = None
    signatory_poa_date: Optional[date] = None
    signatory_poa_start_date: Optional[date] = None
    signatory_poa_end_date: Optional[date] = None
    signatory_signing_date: Optional[datetime] = None
    broker_doc_kind_code: Optional[str] = None
    broker_contract_doc_kind_code: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None


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
    special_ref_code: Optional[str] = None
    country_dispatch_code: Optional[str]
    country_origin_name: Optional[str] = None
    country_destination_code: Optional[str]
    transport_at_border: Optional[str]
    container_info: Optional[str]
    incoterms_code: Optional[str]
    transport_on_border: Optional[str]
    currency_code: Optional[str]
    total_invoice_value: Optional[Decimal]
    exchange_rate: Optional[Decimal]
    deal_nature_code: Optional[str]
    deal_specifics_code: Optional[str] = None
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
    trading_country_code: Optional[str] = None
    declarant_inn_kpp: Optional[str] = None
    declarant_ogrn: Optional[str] = None
    declarant_phone: Optional[str] = None
    delivery_place: Optional[str] = None
    transport_on_border_id: Optional[str] = None
    entry_customs_code: Optional[str] = None
    goods_location: Optional[str] = None
    payment_deferral: Optional[str] = None
    warehouse_requisites: Optional[str] = None
    transit_offices: Optional[str] = None
    destination_office_code: Optional[str] = None
    processing_status: Optional[str] = None
    signature_status: str = "unsigned"
    evidence_map: Optional[dict[str, Any]] = None
    ai_confidence: Optional[Decimal] = None
    ai_issues: Optional[list[dict]] = None
    freight_amount: Optional[Decimal] = None
    freight_currency: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_position: Optional[str] = None
    signatory_id_doc: Optional[str] = None
    signatory_cert_number: Optional[str] = None
    signatory_power_of_attorney: Optional[str] = None
    broker_registry_number: Optional[str] = None
    broker_contract_number: Optional[str] = None
    broker_contract_date: Optional[datetime] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None
    transport_reg_number: Optional[str] = None
    transport_nationality_code: Optional[str] = None
    goods_location_code: Optional[str] = None
    goods_location_customs_code: Optional[str] = None
    goods_location_zone_id: Optional[str] = None
    goods_location_info_type_code: Optional[str] = None
    goods_location_svh_doc_id: Optional[str] = None
    goods_location_address: Optional[str] = None
    border_customs_name: Optional[str] = None
    border_customs_country_code: Optional[str] = None
    transport_kind_code: Optional[str] = None
    transport_type_name: Optional[str] = None
    transport_means_quantity: Optional[int] = None
    signatory_surname: Optional[str] = None
    signatory_first_name: Optional[str] = None
    signatory_middle_name: Optional[str] = None
    signatory_phone: Optional[str] = None
    signatory_email: Optional[str] = None
    signatory_id_card_code: Optional[str] = None
    signatory_id_card_series: Optional[str] = None
    signatory_id_card_number: Optional[str] = None
    signatory_id_card_date: Optional[date] = None
    signatory_id_card_org: Optional[str] = None
    signatory_poa_number: Optional[str] = None
    signatory_poa_date: Optional[date] = None
    signatory_poa_start_date: Optional[date] = None
    signatory_poa_end_date: Optional[date] = None
    signatory_signing_date: Optional[datetime] = None
    broker_doc_kind_code: Optional[str] = None
    broker_contract_doc_kind_code: Optional[str] = None
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
    processing_status: Optional[str] = None
    signature_status: str = "unsigned"
    company_id: uuid.UUID
    total_invoice_value: Optional[Decimal]
    currency_code: Optional[str]
    total_items_count: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class StatusChangeRequest(BaseModel):
    new_status: str
