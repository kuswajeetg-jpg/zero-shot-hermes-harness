"""Auth routes — register/login with JWT."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api._common import api_error, ok
from src.config.settings import get_settings
from src.db.models import Base, User
from src.db.session import get_session, init_db
from src.domain.analyst import AuthRequest, AuthResponse
from src.observability.events import get_logger

import hashlib
import hmac
import os

router = APIRouter()


def _hash(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return "sha256:" + salt.hex() + ":" + digest.hex()


def _verify(password: str, hashed: str) -> bool:
    if not hashed or not hashed.startswith("sha256:"):
        return False
    try:
        _, salt_hex, digest_hex = hashed.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(expected, actual)


def _create_access_token(user_id: str) -> str:
    from jose import jwt
    s = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=s.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, s.secret_key, algorithm=s.algorithm)


@router.post("/auth/register")
def register(req: AuthRequest, session: Session = Depends(get_session)) -> dict:
    init_db()
    existing = session.query(User).filter(User.email == req.email).first()
    if existing:
        raise api_error("email_exists", "Email already registered", 409)
    user = User(email=req.email, hashed_password=_hash(req.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    get_logger("auth").info("user_registered", user_id=user.id)
    return ok({"user_id": user.id, "email": user.email})


@router.post("/auth/login", response_model=None)
def login(req: AuthRequest, session: Session = Depends(get_session)) -> dict:
    init_db()
    user = session.query(User).filter(User.email == req.email).first()
    if not user or not _verify(req.password, user.hashed_password or ""):
        raise api_error("invalid_credentials", "Invalid email or password", 401)
    token = _create_access_token(user.id)
    get_logger("auth").info("user_login", user_id=user.id)
    return ok(AuthResponse(access_token=token).model_dump())
