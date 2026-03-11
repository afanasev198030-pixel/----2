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
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    postal_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CounterpartyUpdate(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    country_code: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    address: Optional[str] = None
    company_id: Optional[uuid.UUID] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    postal_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


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
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    postal_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[CompanyResponse] = None
