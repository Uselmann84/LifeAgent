"""FastAPI application entrypoint.

Boots in Demo Mode by default. Runs migrations on startup. Wires routers. Structured, redacted
error handling ensures secrets and personal content never leak into error payloads.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_agent,
    routes_approvals,
    routes_autonomy,
    routes_cleanup,
    routes_email,
    routes_health,
    routes_pairing,
    routes_tasks_cases,
    routes_today,
)
from app.core.config import get_settings
from app.core.db import run_migrations
from app.core.versions import BACKEND_VERSION


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Life Agent Backend",
        version=BACKEND_VERSION,
        lifespan=lifespan,
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    for module in (
        routes_health,
        routes_agent,
        routes_today,
        routes_tasks_cases,
        routes_email,
        routes_cleanup,
        routes_approvals,
        routes_pairing,
        routes_autonomy,
    ):
        app.include_router(module.router)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = str(uuid.uuid4())
        # Never include secrets or personal content in the error payload.
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "correlation_id": correlation_id,
                }
            },
        )

    return app


app = create_app()
