"""Auth — email+password signup/login (JWT sessions) + API-key issuance.

Two ways in, one user record:
  * **Email + password** → a JWT session (the product login shell).
  * **API key** (`nxs_…`, shown once at signup) → header auth for programmatic use.

Passwords and API keys are both stored only as salted PBKDF2 hashes (stdlib, no
bcrypt wheel). API keys also carry a non-secret indexed id so header auth is an
O(1) lookup + a single verify, not an O(n) scan over every user.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.api.schemas import (AuthResponse, LoginRequest, RegisterRequest,
                             RegisterResponse, SignupRequest, TokenRequest,
                             TokenResponse, UserPublic)
from app.core.security import (api_key_id, create_jwt, hash_secret, new_api_key,
                              verify_secret)
from app.db.app_store import get_store

router = APIRouter(prefix="/auth", tags=["auth"])


def _public(user: dict) -> UserPublic:
    return UserPublic(id=user["id"], email=user["email"],
                      plan=user.get("plan") or "free")


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest):
    """Create an account with email + password. Returns a JWT session and a
    one-time API key for programmatic access."""
    email = req.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "enter a valid email address")
    store = get_store()
    if store.get_user_by_email(email):
        raise HTTPException(409, "email already registered")
    api_key = new_api_key()
    user = store.create_user(
        email, api_key_hash=hash_secret(api_key),
        password_hash=hash_secret(req.password), api_key_id=api_key_id(api_key))
    store.append_audit("user.signup", actor=user["id"], verdict="ALLOW")
    return AuthResponse(access_token=create_jwt(user["id"], {"email": email}),
                        user=_public(user), api_key=api_key)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    email = req.email.strip().lower()
    store = get_store()
    user = store.get_user_by_email(email)
    if not user or not user.get("password_hash") or \
            not verify_secret(req.password, user["password_hash"]):
        raise HTTPException(401, "invalid email or password")
    return AuthResponse(access_token=create_jwt(user["id"], {"email": email}),
                        user=_public(user))


@router.get("/me", response_model=UserPublic)
def me(user: dict | None = Depends(get_current_user)):
    if not user:
        raise HTTPException(401, "not authenticated")
    full = get_store().get_user(user["id"]) or user
    return _public(full)


# --- legacy API-key-only flow (kept for backward compatibility) --------------
@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    store = get_store()
    email = req.email.strip().lower()
    if store.get_user_by_email(email):
        raise HTTPException(409, "email already registered")
    api_key = new_api_key()
    user = store.create_user(email, api_key_hash=hash_secret(api_key),
                             api_key_id=api_key_id(api_key))
    return RegisterResponse(user_id=user["id"], email=user["email"], api_key=api_key)


@router.post("/token", response_model=TokenResponse)
def token(req: TokenRequest):
    store = get_store()
    user = store.get_user_by_email(req.email.strip().lower())
    if not user or not verify_secret(req.api_key, user["api_key_hash"]):
        raise HTTPException(401, "invalid credentials")
    return TokenResponse(access_token=create_jwt(user["id"], {"email": user["email"]}))
