"""Task and case endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, desc, select

from app.agent import tools
from app.api.deps import get_session, require
from app.api.schemas import CaseCreate, CaseUpdate, TaskCreate, TaskUpdate
from app.core.models import Case, EmailMessage, Priority, Task, utcnow

router = APIRouter(prefix="/api/v1", tags=["tasks-cases"])


# ------------------------------------------------------------------------- tasks
@router.get("/tasks", dependencies=[Depends(require("manage_tasks"))])
def list_tasks(session: Session = Depends(get_session)) -> dict:
    rows = session.exec(select(Task).order_by(desc(Task.created_at))).all()
    return {"items": [t.model_dump() for t in rows]}


@router.post("/tasks", dependencies=[Depends(require("manage_tasks"))])
def create_task(body: TaskCreate, session: Session = Depends(get_session)) -> dict:
    task = tools.create_task(
        session,
        title=body.title,
        description=body.description,
        priority=Priority(body.priority),
        due_at=body.due_at,
        case_id=body.case_id,
        source="user",
    )
    return task.model_dump()


@router.get("/tasks/{task_id}", dependencies=[Depends(require("manage_tasks"))])
def get_task(task_id: str, session: Session = Depends(get_session)) -> dict:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump()


@router.patch("/tasks/{task_id}", dependencies=[Depends(require("manage_tasks"))])
def update_task(task_id: str, body: TaskUpdate, session: Session = Depends(get_session)) -> dict:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    task.updated_at = utcnow()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task.model_dump()


# ------------------------------------------------------------------------- cases
@router.get("/cases", dependencies=[Depends(require("manage_cases"))])
def list_cases(status: str | None = None, session: Session = Depends(get_session)) -> dict:
    stmt = select(Case).order_by(desc(Case.created_at))
    if status:
        stmt = stmt.where(Case.status == status)
    rows = session.exec(stmt).all()
    return {"items": [c.model_dump() for c in rows]}


@router.post("/cases", dependencies=[Depends(require("manage_cases"))])
def create_case(body: CaseCreate, session: Session = Depends(get_session)) -> dict:
    case = tools.create_case(
        session,
        case_type=body.case_type,
        title=body.title,
        desired_outcome=body.desired_outcome,
        background=body.background,
    )
    return case.model_dump()


@router.get("/cases/{case_id}", dependencies=[Depends(require("manage_cases"))])
def get_case(case_id: str, session: Session = Depends(get_session)) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.model_dump()


@router.patch("/cases/{case_id}", dependencies=[Depends(require("manage_cases"))])
def update_case(case_id: str, body: CaseUpdate, session: Session = Depends(get_session)) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    case.updated_at = utcnow()
    session.add(case)
    session.commit()
    session.refresh(case)
    return case.model_dump()


@router.post("/cases/from-email/{email_id}", dependencies=[Depends(require("manage_cases"))])
def case_from_email(email_id: str, session: Session = Depends(get_session)) -> dict:
    email = session.get(EmailMessage, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    case = tools.create_case(
        session,
        case_type="other",
        title=email.subject[:80],
        background=email.body[:1000],
    )
    email.case_id = case.id
    session.add(email)
    session.commit()
    return case.model_dump()
