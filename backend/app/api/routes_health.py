"""Health and version endpoints."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends

from app.agent.llm.factory import get_llm_provider
from app.api.deps import get_caller
from app.core.config import Settings, get_settings
from app.core.db import current_schema_version
from app.core.versions import API_VERSION, BACKEND_VERSION, MIN_COMPATIBLE_IOS_VERSION

router = APIRouter(prefix="/api/v1", tags=["health"])

_START = time.time()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "mode": settings.mode.value,
        "environment": settings.env.value,
        "backend_version": BACKEND_VERSION,
        "api_version": API_VERSION,
        "db_schema_version": f"{current_schema_version():03d}",
        "min_compatible_ios_version": MIN_COMPATIBLE_IOS_VERSION,
        "uptime_seconds": round(time.time() - _START, 1),
    }


@router.get("/health/model", dependencies=[Depends(get_caller)])
def model_health() -> dict:
    provider = get_llm_provider()
    health = asyncio.run(provider.health_check())
    return {
        "provider": health.provider,
        "reachable": health.reachable,
        "profiles_loaded": health.profiles_loaded,
        "latency_ms": health.latency_ms,
        "detail": health.detail,
    }
