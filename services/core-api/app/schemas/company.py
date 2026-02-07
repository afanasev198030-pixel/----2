import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CompanyCreate(BaseModel):
    name: str
    inn: str
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    address: Optional[str] = None
    country_code: Optional[str] = "RU"


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    address: Optional[str] = None
    country_code: Optional[str] = None


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    inn: Optional[str]
    kpp: Optional[str]
    ogrn: Optional[str]
    address: Optional[str]
    country_code: Optional[str]
    created_at: Optional[datetime]
