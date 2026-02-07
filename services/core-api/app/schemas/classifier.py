import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ClassifierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    classifier_type: str
    code: str
    name_ru: Optional[str]
    name_en: Optional[str]
    parent_code: Optional[str]
    meta: Optional[dict]
    is_active: bool
