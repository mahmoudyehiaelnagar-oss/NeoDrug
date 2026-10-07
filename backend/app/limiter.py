from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request
from . import models

FREE_LIMITS = {
    "ai_chat": 5,
    "single_ocr": 1,
    "dual_ocr": 0
}

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def get_or_create_usage(db: Session, user: Optional[models.User], client_ip: str) -> models.UsageRecord:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    if user:
        record = db.query(models.UsageRecord).filter(
            models.UsageRecord.user_id == user.id,
            models.UsageRecord.date_str == today_str
        ).first()
        if not record:
            record = models.UsageRecord(
                user_id=user.id,
                date_str=today_str,
                ai_queries_count=0,
                single_ocr_count=0,
                dual_ocr_count=0
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        return record
    else:
        record = db.query(models.UsageRecord).filter(
            models.UsageRecord.client_ip == client_ip,
            models.UsageRecord.date_str == today_str
        ).first()
        if not record:
            record = models.UsageRecord(
                client_ip=client_ip,
                date_str=today_str,
                ai_queries_count=0,
                single_ocr_count=0,
                dual_ocr_count=0
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        return record

def check_feature_access(db: Session, user: Optional[models.User], feature: str, client_ip: str) -> Tuple[bool, Dict[str, Any]]:
    # 1. Check if user has active PRO
    if user and user.tier == "pro":
        if not user.pro_expires_at or user.pro_expires_at > datetime.utcnow():
            return True, {"tier": "pro", "unlimited": True}
        else:
            user.tier = "free"
            db.commit()

    # 2. Check Free Tier usage limits
    usage = get_or_create_usage(db, user, client_ip)

    if feature == "dual_ocr":
        return False, {
            "error": "PRO_REQUIRED",
            "feature": "dual_ocr",
            "message": "فحص الروشتة مع التحاليل وتدقيق الجرعات ميزة حصرية لمشتركي Neo PRO.",
            "limit": 0,
            "used": usage.dual_ocr_count,
            "upgrade_required": True
        }

    elif feature == "single_ocr":
        if usage.single_ocr_count >= FREE_LIMITS["single_ocr"]:
            return False, {
                "error": "LIMIT_REACHED",
                "feature": "single_ocr",
                "message": f"لقد استنفدت الحد اليومي المجاني لقراءة الروشتات ({FREE_LIMITS['single_ocr']} فحص يومياً). قم بالترقية لـ PRO للاستخدام غير المحدود.",
                "limit": FREE_LIMITS["single_ocr"],
                "used": usage.single_ocr_count,
                "upgrade_required": True
            }

    elif feature == "ai_chat":
        if usage.ai_queries_count >= FREE_LIMITS["ai_chat"]:
            return False, {
                "error": "LIMIT_REACHED",
                "feature": "ai_chat",
                "message": f"لقد استنفدت رصيدك اليومي المجاني ({FREE_LIMITS['ai_chat']} استشارات يومياً). قم بالترقية لـ PRO للاستخدام غير المحدود.",
                "limit": FREE_LIMITS["ai_chat"],
                "used": usage.ai_queries_count,
                "upgrade_required": True
            }

    return True, {"tier": "free", "unlimited": False}

def record_feature_usage(db: Session, user: Optional[models.User], feature: str, client_ip: str):
    usage = get_or_create_usage(db, user, client_ip)
    if feature == "dual_ocr":
        usage.dual_ocr_count += 1
    elif feature == "single_ocr":
        usage.single_ocr_count += 1
    elif feature == "ai_chat":
        usage.ai_queries_count += 1
    db.commit()

def seed_default_promo_codes(db: Session):
    default_codes = [
        {"code": "NEOPRO", "duration_days": 30, "max_uses": None},
        {"code": "VIP2026", "duration_days": 90, "max_uses": None},
        {"code": "PHARMA2026", "duration_days": 365, "max_uses": None},
        {"code": "TRIAL2026", "duration_days": 7, "max_uses": None},
    ]
    for item in default_codes:
        existing = db.query(models.PromoCode).filter(models.PromoCode.code == item["code"]).first()
        if not existing:
            new_code = models.PromoCode(
                code=item["code"],
                tier_granted="pro",
                duration_days=item["duration_days"],
                max_uses=item["max_uses"],
                is_active=True
            )
            db.add(new_code)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
