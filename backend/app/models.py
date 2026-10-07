from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from .database import Base

class Drug(Base):
    __tablename__ = "drugs"

    id = Column(Integer, primary_key=True, index=True)
    trade_en = Column(String, index=True)
    trade_ar = Column(String, index=True, nullable=True)
    generic_en = Column(String, index=True, nullable=True)
    generic_ar = Column(String, nullable=True)
    form = Column(String, index=True, nullable=True)
    form_ar = Column(String, nullable=True)
    strength = Column(String, nullable=True)
    cls = Column(String, index=True, nullable=True)
    indications = Column(String, nullable=True)
    dosage = Column(String, nullable=True)
    side_effects = Column(String, nullable=True)
    contraindications = Column(String, nullable=True)
    pregnancy = Column(String, nullable=True)

    # Store alternates as a JSON array natively.
    alternates = Column(JSON, nullable=True, default=list)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user") # 'user', 'admin'
    tier = Column(String, default="free") # 'free', 'pro'
    pro_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
    redemptions = relationship("PromoRedemption", back_populates="user", cascade="all, delete-orphan")

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    client_ip = Column(String, nullable=True, index=True)
    date_str = Column(String, index=True, nullable=False) # 'YYYY-MM-DD'
    ai_queries_count = Column(Integer, default=0)
    single_ocr_count = Column(Integer, default=0)
    dual_ocr_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="usage_records")
    __table_args__ = (
        UniqueConstraint('user_id', 'date_str', name='uq_user_date'),
        UniqueConstraint('client_ip', 'date_str', name='uq_ip_date'),
    )

class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    tier_granted = Column(String, default="pro")
    duration_days = Column(Integer, default=30)
    max_uses = Column(Integer, nullable=True) # None = unlimited
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    redemptions = relationship("PromoRedemption", back_populates="promo_code")

class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False, index=True)
    code_used = Column(String, nullable=False)
    redeemed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="redemptions")
    promo_code = relationship("PromoCode", back_populates="redemptions")

    __table_args__ = (
        UniqueConstraint('user_id', 'promo_code_id', name='uq_user_promo_redemption'),
    )
