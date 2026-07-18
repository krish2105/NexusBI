"""Nexus BI — FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (auth, briefing, connections, conversations, dashboards,
                     insights, metrics, misc, monitors, query, uploads)
from app.config import settings
from app.core.tracing import flush as flush_traces
from app.core.tracing import is_enabled as tracing_enabled
from app.db.app_store import get_store
from app.db.seed_demo import seed_sqlite

logging.basicConfig(level=logging.INFO,
                    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger("nexus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the demo target DB exists (idempotent) and app store is initialized.
    if settings.demo_target_url.startswith("sqlite"):
        try:
            seed_sqlite()
        except Exception as e:  # noqa: BLE001
            log.warning(f"demo seed skipped: {e}")
    get_store()  # init app schema
    log.info(f"Nexus BI ready — LLM provider resolved, 5-layer SQL guard active, "
             f"tracing={'on' if tracing_enabled() else 'off'}")
    yield
    flush_traces()  # send any pending trace batches before the process exits


app = FastAPI(
    title="Nexus BI API",
    description="Autonomous Business Analyst Copilot — NL question -> safe SQL -> "
                "chart -> forecast -> narrated insight.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"] if settings.environment == "local"
    else settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Never leak internals or raw SQL errors to untrusted callers.
    log.error(f"unhandled error on {request.url.path}: {exc!r}")
    return JSONResponse(status_code=500,
                        content={"error": "internal_error",
                                 "detail": "An unexpected error occurred."})


for r in (auth.router, connections.router, uploads.router, query.router,
          conversations.router, dashboards.router, insights.router,
          metrics.router, monitors.router, briefing.router, misc.router):
    app.include_router(r)


@app.get("/", tags=["meta"])
def root():
    return {"name": settings.app_name,
            "tagline": "Ask your data anything.",
            "docs": "/docs", "health": "/health"}
