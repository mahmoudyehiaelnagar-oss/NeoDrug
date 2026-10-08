from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

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
    message: Optional[str] = ""
    image_base64: Optional[str] = None
    images: Optional[List[str]] = []
    prescription_image: Optional[str] = None
    lab_image: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = []

class InteractionRequest(BaseModel):
    drugs: List[str]

# --- Auth and Subscription Schemas ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    username: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class UserProfileResponse(BaseModel):
    id: int
    email: str
    username: Optional[str] = None
    tier: str
    is_pro: bool
    pro_expires_at: Optional[datetime] = None
    days_left: Optional[int] = None
    ai_queries_used: int = 0
    ai_queries_limit: int = 5
    single_ocr_used: int = 0
    single_ocr_limit: int = 1
    dual_ocr_used: int = 0
    dual_ocr_limit: int = 0
    is_unlimited: bool = False

    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    token: str
    user: UserProfileResponse
    message: str

class RedeemRequest(BaseModel):
    code: str

class RedeemResponse(BaseModel):
    success: bool
    message: str
    tier: str
    duration_days: int
    pro_expires_at: Optional[datetime] = None

# --- Admin Dashboard Schemas ---

class AdminUpdateUserTierRequest(BaseModel):
    user_id: int
    tier: str # 'free', 'pro'
    duration_days: Optional[int] = 30 # For PRO: 30, 90, 365, or 36500 for lifetime

class AdminCreatePromoRequest(BaseModel):
    code: str
    duration_days: int = 30
    max_uses: Optional[int] = None # None = unlimited
    tier_granted: str = "pro"

class AdminPromoItem(BaseModel):
    id: int
    code: str
    tier_granted: str
    duration_days: int
    max_uses: Optional[int] = None
    used_count: int
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AdminUserItem(BaseModel):
    id: int
    email: str
    username: Optional[str] = None
    role: str
    tier: str
    is_pro: bool
    pro_expires_at: Optional[datetime] = None
    days_left: Optional[int] = None
    created_at: Optional[datetime] = None
    today_ai_used: int = 0
    today_ocr_used: int = 0

    class Config:
        from_attributes = True

class AdminStatsResponse(BaseModel):
    total_users: int
    pro_users: int
    free_users: int
    total_promos: int
    today_ai_queries: int
    today_ocr_scans: int
    total_drugs: int
