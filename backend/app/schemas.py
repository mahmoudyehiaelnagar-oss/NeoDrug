from pydantic import BaseModel
from typing import List, Optional

class DrugBase(BaseModel):
    trade_en: Optional[str] = None
    trade_ar: Optional[str] = None
    generic_en: Optional[str] = None
    generic_ar: Optional[str] = None
    form: Optional[str] = None
    form_ar: Optional[str] = None
    strength: Optional[str] = None
    cls: Optional[str] = None
    indications: Optional[str] = None
    dosage: Optional[str] = None
    side_effects: Optional[str] = None
    contraindications: Optional[str] = None
    pregnancy: Optional[str] = None
    alternates: Optional[List[str]] = []

class DrugResponse(DrugBase):
    id: int

    class Config:
        from_attributes = True

class PaginatedDrugs(BaseModel):
    items: List[DrugResponse]
    total: int
    page: int
    size: int
    pages: int

class ChatRequest(BaseModel):
    message: str
    image_base64: Optional[str] = None

class InteractionRequest(BaseModel):
    drugs: List[str]
