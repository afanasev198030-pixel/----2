import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict

from .company import CompanyResponse


class CounterpartyCreate(BaseModel):
    type: str
    name: str
    country_code: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    address: Optional[str] = None
    company_id: uuid.UUID


class CounterpartyUpdate(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    country_code: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    address: Optional[str] = None
    company_id: Optional[uuid.UUID] = None


class CounterpartyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    name: str
    country_code: Optional[str]
    registration_number: Optional[str]
    tax_number: Optional[str]
    address: Optional[str]
    company_id: uuid.UUID
    company: Optional[CompanyResponse] = None
