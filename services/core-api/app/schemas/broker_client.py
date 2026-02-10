import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ConfigDict

from .company import CompanyResponse, CompanyCreate


class BrokerClientCreate(BaseModel):
    """Create a broker-client relationship. Either provide existing client_company_id
    or inline new_company to create a new company."""

    client_company_id: Optional[uuid.UUID] = None
    new_company: Optional[CompanyCreate] = None
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None
    tariff_plan: str = "standard"


class BrokerClientUpdate(BaseModel):
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None
    tariff_plan: Optional[str] = None
    is_active: Optional[bool] = None


class BrokerClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    broker_company_id: uuid.UUID
    client_company_id: uuid.UUID
    contract_number: Optional[str]
    contract_date: Optional[date]
    tariff_plan: Optional[str]
    is_active: bool
    created_at: Optional[datetime]
    client_company: Optional[CompanyResponse] = None
