"""Autonomy status and simulation endpoints (Sections 35.4 & 35.9).

``GET /api/v1/autonomy/status`` reports the health of the six autonomous services and whether real
side effects are permitted (only true on the Backend Mac in production execution).

``POST /api/v1/autonomy/tick`` runs a single loop tick and returns the decisions. It is restricted
to simulation execution so proactive behavior can be exercised safely on the Development Mac; on a
production backend it responds 409 because the launchd runtime owns the loop.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_caller, get_session
from app.autonomy.runtime import AutonomousRuntime
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/autonomy", tags=["autonomy"], dependencies=[Depends(get_caller)])


@router.get("/status")
def autonomy_status(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    runtime = AutonomousRuntime(session, settings)
    snap = runtime.status()
    return {
        "execution_mode": snap.execution_mode,
        "running": snap.running,
        "ticks": snap.ticks,
        "events_processed": snap.events_processed,
        "last_tick_at": snap.last_tick_at,
        "side_effects_permitted": snap.side_effects_permitted,
        "services": [asdict(c) for c in snap.components],
    }


@router.post("/tick")
def autonomy_tick(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.is_simulation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Manual ticks are only allowed in simulation; the launchd runtime owns the "
            "production loop.",
        )
    runtime = AutonomousRuntime(session, settings)
    decisions = runtime.tick()
    return {
        "processed": len(decisions),
        "decisions": [asdict(d) for d in decisions],
    }
