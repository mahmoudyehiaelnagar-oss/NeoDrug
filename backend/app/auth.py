import os
import time
import json
import base64
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from .database import get_db
from . import models

JWT_SECRET = os.getenv("JWT_SECRET", "neo-drug-production-secure-key-2026-auth-pro-vault")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRATION_DAYS = 30

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 100_000
    derived_key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    return f"pbkdf2:sha256:{iterations}${salt}${derived_key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        parts = hashed_password.split('$')
        if len(parts) != 3:
            return False
        meta, salt, stored_hash = parts
        _, _, iter_str = meta.split(':')
        iterations = int(iter_str)

        derived_key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        return hmac.compare_digest(derived_key.hex(), stored_hash)
    except Exception:
        return False

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _b64url_decode(data_str: str) -> bytes:
    padding = '=' * ((4 - len(data_str) % 4) % 4)
    return base64.urlsafe_b64decode(data_str + padding)

def create_jwt_token(payload: Dict[str, Any], expires_days: int = TOKEN_EXPIRATION_DAYS) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    now = int(time.time())
    payload_copy = payload.copy()
    payload_copy["iat"] = now
    payload_copy["exp"] = now + (expires_days * 86400)

    header_b64 = _b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _b64url_encode(json.dumps(payload_copy, separators=(',', ':')).encode('utf-8'))
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')

    signature = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
        if "exp" in payload and payload["exp"] < int(time.time()):
            return None

        return payload
    except Exception:
        return None

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    payload = decode_jwt_token(token)
    if not payload or "sub" not in payload:
        return None

    user_id = payload["sub"]
    email = payload.get("email")
    tier_from_jwt = payload.get("tier", "free")
    exp_str = payload.get("pro_expires_at")
    jwt_pro_exp = None
    if exp_str:
        try:
            jwt_pro_exp = datetime.fromisoformat(exp_str)
        except Exception:
            pass

    user = None
    if isinstance(user_id, int) and user_id > 0:
        user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user and email:
        user = db.query(models.User).filter(models.User.email == email).first()

    # Vercel Serverless Sync: If container was recreated and user not in /tmp SQLite, restore from verified JWT
    if not user and email:
        user = models.User(
            email=email,
            username=payload.get("username") or email.split("@")[0],
            password_hash="verified_jwt_session",
            role=payload.get("role", "user"),
            tier=tier_from_jwt,
            pro_expires_at=jwt_pro_exp
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user = db.query(models.User).filter(models.User.email == email).first()

    if user:
        # If verified JWT holds an active PRO tier newer than DB, sync to DB
        if tier_from_jwt == "pro" and jwt_pro_exp and (not user.pro_expires_at or jwt_pro_exp > user.pro_expires_at):
            user.tier = "pro"
            user.pro_expires_at = jwt_pro_exp
            try:
                db.commit()
            except Exception:
                db.rollback()

        # Check expiration
        if user.tier == "pro" and user.pro_expires_at:
            if user.pro_expires_at < datetime.utcnow():
                user.tier = "free"
                try:
                    db.commit()
                except Exception:
                    db.rollback()

    return user

def get_current_user_required(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="يرجى تسجيل الدخول للوصول إلى هذه الميزة.")
    return user
