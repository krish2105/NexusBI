"""Central configuration (pydantic-settings).

All defaults keep the project on the free tier and runnable with **zero API keys**.
The system degrades gracefully: no GROQ_API_KEY -> deterministic planner/narrator;
no Postgres -> SQLite demo seeded from the real Olist CSVs.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data" / "olist"
VAR_DIR = BACKEND_ROOT / "var"
VAR_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App identity ---
    app_name: str = "Nexus BI"
    environment: Literal["local", "production"] = "local"
    api_prefix: str = ""

    # --- Security ---
    jwt_secret: str = Field(default="dev-insecure-change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    encryption_key: str | None = None          # for DSN encryption at rest
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    # Allow connections to loopback/private hosts (dev only). Off = SSRF-safe.
    allow_local_targets: bool = False
    # Require a valid API key / JWT to create connections & run custom queries.
    # The bundled demo connection always stays open so the public demo works.
    require_auth: bool = False
    # Per-client rate limit on /query (requests per window seconds).
    rate_limit_requests: int = 30
    rate_limit_window_s: int = 60

    # --- App metadata DB (connections, history, dashboards, audit) ---
    # Default: local SQLite file. Production: set to a Supabase Postgres URL.
    app_db_url: str = Field(default=f"sqlite:///{VAR_DIR / 'nexus_app.db'}")

    # --- Target (user) demo DB ---
    # Default: instant SQLite seeded from the real CSVs. For the Postgres
    # production path, set demo_target_url to a read-only Postgres DSN.
    demo_target_url: str = Field(default=f"sqlite:///{VAR_DIR / 'nexus_demo.db'}")
    target_statement_timeout_s: int = 8
    target_row_cap: int = 10_000

    # --- LLM (all optional; free tier only) ---
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str | None = None  # e.g. http://localhost:11434
    ollama_model: str = "llama3.1:8b"
    # When no key is configured we use the deterministic engine.
    llm_provider: Literal["auto", "groq", "ollama", "deterministic"] = "auto"

    # --- RAG ---
    use_embeddings: bool = False  # local bge-small if installed; else keyword hybrid
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    retrieval_k: int = 8

    # --- ML ---
    forecast_min_points: int = 6
    forecast_horizon: int = 6

    # --- CSV upload (bring-your-own-data) safety caps ---
    max_upload_mb: int = 25
    max_rows_per_table: int = 200_000
    max_columns_per_table: int = 80
    max_tables_per_upload: int = 10

    # --- Observability (optional free tier) ---
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def data_dir(self) -> Path:
        return DATA_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
