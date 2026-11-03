import os
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import Request
from . import models

FREE_LIMITS = {
    "ai_chat": 5,
    "single_ocr": 2,     # 2 free daily prescription OCR scans for trial
    "dual_ocr": 0       # Locked for non-PRO subscribers
}

def get_client_ip(request: Request) -> str:
    """
    Resolve the client IP without trusting a client-supplied X-Forwarded-For.

    The hosting proxy (Vercel) sets x-real-ip / x-vercel-forwarded-for. We only fall
    back to the *last* X-Forwarded-For entry (the one appended by the proxy) and
    finally to the socket address.
    """
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip

    vercel_ip = (request.headers.get("x-vercel-forwarded-for") or "").strip()
    if vercel_ip:
        return vercel_ip.split(",")[-1].strip()

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-1]

    return request.client.host if request.client else "127.0.0.1"

def get_or_create_usage(db: Session, user: Optional[models.User], client_ip: str) -> models.UsageRecord:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    if user:
        filters = (
            models.UsageRecord.user_id == user.id,
            models.UsageRecord.date_str == today_str,
        )
        new_record = models.UsageRecord(user_id=user.id, date_str=today_str)
    else:
        filters = (
            models.UsageRecord.client_ip == client_ip,
            models.UsageRecord.date_str == today_str,
        )
        new_record = models.UsageRecord(client_ip=client_ip, date_str=today_str)

    record = db.query(models.UsageRecord).filter(*filters).first()
    if record:
        return record

    db.add(new_record)
    try:
        db.commit()
    except IntegrityError:
        # Another request created today's row first; reuse it instead of failing.
        db.rollback()
        record = db.query(models.UsageRecord).filter(*filters).first()
        if not record:
            raise
        return record
    except Exception:
        db.rollback()
        raise

    db.refresh(new_record)
    return new_record

def check_feature_access(db: Session, user: Optional[models.User], feature: str, client_ip: str) -> Tuple[bool, Dict[str, Any]]:
    # 1. Check if user has active PRO subscription
    if user and user.tier == "pro":
        if not user.pro_expires_at or user.pro_expires_at > datetime.utcnow():
            days_left = max(1, (user.pro_expires_at - datetime.utcnow()).days) if user.pro_expires_at else 9999
            return True, {"tier": "pro", "unlimited": True, "days_left": days_left}
        else:
            user.tier = "free"
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                raise e

    # 2. Check Free Tier usage limits
    usage = get_or_create_usage(db, user, client_ip)

    if feature == "dual_ocr":
        return False, {
            "error": "PRO_REQUIRED",
            "feature": "dual_ocr",
            "message": "🔒 فحص الروشتة مع التحاليل المخبرية وتدقيق الجرعات ميزة حصرية لمشتركي Neo Drug PRO.",
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
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def seed_default_promo_codes(db: Session):
    """
    Seed promo codes only from an explicit DEFAULT_PROMO_CODES env var.

    We deliberately do NOT ship public, unlimited promo codes in the source code:
    anyone reading the repository could grant themselves a free lifetime PRO plan.

    Expected format (JSON array):
      DEFAULT_PROMO_CODES=[{"code":"TRIAL7","duration_days":7,"max_uses":100}]
    """
    raw = (os.getenv("DEFAULT_PROMO_CODES") or "").strip()
    if not raw:
        return

    try:
        default_codes = json.loads(raw)
    except Exception as exc:
        print(f"Invalid DEFAULT_PROMO_CODES JSON: {exc}")
        return

    if not isinstance(default_codes, list):
        print("Invalid DEFAULT_PROMO_CODES: expected a JSON array")
        return

    for item in default_codes:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        code = str(item["code"]).strip().upper()
        existing = db.query(models.PromoCode).filter(models.PromoCode.code == code).first()
        if not existing:
            new_code = models.PromoCode(
                code=code,
                tier_granted="pro",
                duration_days=int(item.get("duration_days") or 30),
                max_uses=item.get("max_uses"),
                is_active=True
            )
            db.add(new_code)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
