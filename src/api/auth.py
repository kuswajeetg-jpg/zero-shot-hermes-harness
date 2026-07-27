"""Auth routes — register/login with JWT and RBAC helpers."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
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
from jose import JWTError, jwt

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
    s = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=s.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, s.secret_key, algorithm=s.algorithm)


def _decode_access_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


class CurrentUser:
    __slots__ = ("user_id", "email", "role", "token")

    def __init__(self, user_id: str, email: str, role: str, token: str) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role
        self.token = token


def get_current_user(request: Request, session: Session = Depends(get_session)) -> CurrentUser:
    auth = request.headers.get("authorization") or ""
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    payload = _decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return CurrentUser(user_id=user.id, email=user.email, role=user.role, token=token)


def require_roles(*allowed: str):
    allowed_set = {r.lower() for r in allowed}

    def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role.lower() not in allowed_set:
            raise HTTPException(status_code=403, detail="Insufficient role privileges")
        return current

    return checker


@router.post("/auth/register")
def register(req: AuthRequest, session: Session = Depends(get_session)) -> dict:
    init_db()
    existing = session.query(User).filter(User.email == req.email).first()
    if existing:
        raise api_error("email_exists", "Email already registered", 409)
    role = "administrator" if "admin" in req.email.lower() else "officer"
    user = User(email=req.email, hashed_password=_hash(req.password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    get_logger("auth").info("user_registered", user_id=user.id)
    return ok({"user_id": user.id, "email": user.email, "role": user.role})


@router.post("/auth/login", response_model=None)
def login(req: AuthRequest, session: Session = Depends(get_session)) -> dict:
    init_db()
    user = session.query(User).filter(User.email == req.email).first()
    if not user or not _verify(req.password, user.hashed_password or ""):
        raise api_error("invalid_credentials", "Invalid email or password", 401)
    
    # Auto-upgrade existing user roles to administrator if they have 'admin' in email
    expected_role = "administrator" if "admin" in req.email.lower() else user.role
    if user.role != expected_role:
        user.role = expected_role
        session.commit()
        session.refresh(user)
        
    token = _create_access_token(user.id)
    get_logger("auth").info("user_login", user_id=user.id)
    return ok({"access_token": token, "token_type": "Bearer", "user_id": user.id, "email": user.email, "role": user.role})
