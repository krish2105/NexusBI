"""Auth — API-key registration and JWT issuance (optional for the demo)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import (RegisterRequest, RegisterResponse, TokenRequest,
                             TokenResponse)
from app.core.security import create_jwt, hash_secret, new_api_key, verify_secret
from app.db.app_store import get_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    store = get_store()
    if store.get_user_by_email(req.email):
        raise HTTPException(409, "email already registered")
    api_key = new_api_key()
    user = store.create_user(req.email, hash_secret(api_key))
    return RegisterResponse(user_id=user["id"], email=user["email"], api_key=api_key)


@router.post("/token", response_model=TokenResponse)
def token(req: TokenRequest):
    store = get_store()
    user = store.get_user_by_email(req.email)
    if not user or not verify_secret(req.api_key, user["api_key_hash"]):
        raise HTTPException(401, "invalid credentials")
    return TokenResponse(access_token=create_jwt(user["id"], {"email": req.email}))
