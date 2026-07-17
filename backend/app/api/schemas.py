"""Pydantic request/response models."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    api_key: str = Field(description="Shown once; store it. Only its hash is kept.")


class TokenRequest(BaseModel):
    email: str
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ConnectionRequest(BaseModel):
    name: str = "Demo — Olist e-commerce"
    target_url: str | None = None      # None -> bundled read-only demo
    read_only_confirmed: bool = True


class GlossaryRequest(BaseModel):
    term: str
    sql_definition: str | None = None
    description: str | None = None


class QueryRequest(BaseModel):
    question: str
    connection_id: str = "demo"


class DashboardRequest(BaseModel):
    name: str


class PinRequest(BaseModel):
    query_id: str
    position: dict[str, Any] | None = None
