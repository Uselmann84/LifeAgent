"""Email endpoints (mock provider in Demo/dev)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.agent import tools
from app.api.deps import get_session, require
from app.api.schemas import EmailDraftRequest, EmailSearch
from app.core.models import EmailMessage
from app.integrations.email.mock import MockEmailProvider

router = APIRouter(prefix="/api/v1/email", tags=["email"])


def _email_dict(m: EmailMessage) -> dict:
    return {
        "id": m.id,
        "thread_id": m.thread_id,
        "sender": m.sender,
        "recipients": m.recipients,
        "subject": m.subject,
        "importance": m.importance.value,
        "why_it_matters": m.why_it_matters,
        "requested_action": m.requested_action,
        "received_at": m.received_at.isoformat(),
        "case_id": m.case_id,
    }


@router.get("/threads", dependencies=[Depends(require("use_integrations"))])
def list_threads(session: Session = Depends(get_session)) -> dict:
    provider = MockEmailProvider(session)
    threads = []
    for tid in provider.list_threads():
        messages = provider.get_thread(tid)
        first = messages[0]
        threads.append(
            {
                "thread_id": tid,
                "subject": first.subject,
                "message_count": len(messages),
                "importance": max(m.importance.value for m in messages),
            }
        )
    return {"items": threads}


@router.get("/threads/{thread_id}", dependencies=[Depends(require("use_integrations"))])
def get_thread(thread_id: str, session: Session = Depends(get_session)) -> dict:
    provider = MockEmailProvider(session)
    messages = provider.get_thread(thread_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread_id": thread_id, "messages": [_email_dict(m) for m in messages]}


@router.post("/search", dependencies=[Depends(require("use_integrations"))])
def search(body: EmailSearch, session: Session = Depends(get_session)) -> dict:
    provider = MockEmailProvider(session)
    return {"items": [_email_dict(m) for m in provider.search(body.query)]}


@router.post("/draft", dependencies=[Depends(require("use_integrations"))])
def draft(body: EmailDraftRequest, session: Session = Depends(get_session)) -> dict:
    intent = body.intent or "follow up"
    email_body = f"Hello,\n\n[Draft — {intent}.]\n\nBest regards"
    result = tools.draft_email(
        session, to=body.to or ["<recipient to confirm>"], subject=body.subject, body=email_body
    )
    return result


@router.post("/{email_id}/classify", dependencies=[Depends(require("use_integrations"))])
def classify(email_id: str, session: Session = Depends(get_session)) -> dict:
    email = session.get(EmailMessage, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return {
        "id": email.id,
        "importance": email.importance.value,
        "why_it_matters": email.why_it_matters,
        "confidence": email.confidence,
    }
