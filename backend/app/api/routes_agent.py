"""Agent chat endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.agent.loop import run_agent
from app.api.deps import get_session, require
from app.api.schemas import ChatRequest

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.post("/chat", dependencies=[Depends(require("chat"))])
def chat(body: ChatRequest, session: Session = Depends(get_session)) -> dict:
    result = run_agent(session, body.message, body.context)
    return result.to_dict()
