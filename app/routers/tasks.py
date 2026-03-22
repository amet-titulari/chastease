from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.services.roleplay_progression import advance_roleplay_state_from_event
from app.services.session_access import get_owned_session
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/sessions", tags=["tasks"])


def _fmt_dt(dt: datetime | None) -> str | None:
    """Serialize a datetime as ISO-8601 with explicit UTC offset.
    SQLite drops tzinfo on read-back, so we re-attach UTC when missing."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    deadline_minutes: int | None = Field(default=None, ge=1)
    consequence_type: str | None = None
    consequence_value: int | None = None
    requires_verification: bool = False
    verification_criteria: str | None = None


class UpdateTaskStatusRequest(BaseModel):
    status: str = Field(pattern="^(completed|failed)$")


@router.post("/{session_id}/tasks")
def create_task(session_id: int, payload: CreateTaskRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    get_owned_session(request, db, session_id)

    deadline_at = None
    if payload.deadline_minutes is not None:
        deadline_at = datetime.now(timezone.utc) + timedelta(minutes=payload.deadline_minutes)

    task = Task(
        session_id=session_id,
        title=payload.title,
        description=payload.description,
        deadline_at=deadline_at,
        consequence_type=payload.consequence_type,
        consequence_value=payload.consequence_value,
        requires_verification=payload.requires_verification,
        verification_criteria=payload.verification_criteria,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {
        "task_id": task.id,
        "status": task.status,
        "title": task.title,
        "deadline_at": _fmt_dt(task.deadline_at),
    }


@router.get("/{session_id}/tasks")
def list_tasks(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    TaskService.evaluate_overdue_tasks(db, session_obj)
    rows = db.query(Task).filter(Task.session_id == session_id).order_by(Task.id.asc()).all()
    return {
        "session_id": session_id,
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "deadline_at": _fmt_dt(row.deadline_at),
                "consequence_type": row.consequence_type,
                "consequence_value": row.consequence_value,
                "consequence_applied_seconds": row.consequence_applied_seconds,
                "consequence_applied_at": str(row.consequence_applied_at) if row.consequence_applied_at else None,
                "requires_verification": bool(row.requires_verification),
                "verification_criteria": row.verification_criteria,
            }
            for row in rows
        ],
    }


@router.post("/{session_id}/tasks/evaluate-overdue")
def evaluate_overdue_tasks(session_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    changed, overdue_ids = TaskService.evaluate_overdue_tasks(db, session_obj)
    return {
        "session_id": session_id,
        "changed_count": changed,
        "overdue_task_ids": overdue_ids,
    }


@router.post("/{session_id}/tasks/{task_id}/status")
def update_task_status(
    session_id: int,
    task_id: int,
    payload: UpdateTaskStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    session_obj = get_owned_session(request, db, session_id)
    task = db.query(Task).filter(Task.id == task_id, Task.session_id == session_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Block direct completion if photo verification is required
    if payload.status == "completed" and task.requires_verification:
        raise HTTPException(
            status_code=409,
            detail="requires_verification",
        )

    task.status = payload.status
    if payload.status == "completed":
        task.completed_at = datetime.now(timezone.utc)
        db.add(
            Message(
                session_id=session_id,
                role="system",
                message_type="task_reward",
                content=f"Task-Reward dokumentiert: task_id={task.id}, title='{task.title}', status=completed",
            )
        )
        advance_roleplay_state_from_event(
            db,
            session_obj,
            event_type="task_completed",
            task_title=task.title,
        )
    if payload.status == "failed":
        TaskService.apply_task_consequence(
            db=db,
            session_obj=session_obj,
            task=task,
            now=datetime.now(timezone.utc),
        )
        advance_roleplay_state_from_event(
            db,
            session_obj,
            event_type="task_failed",
            task_title=task.title,
        )

    db.add(task)
    db.commit()
    db.refresh(task)
    return {
        "task_id": task.id,
        "status": task.status,
        "completed_at": str(task.completed_at) if task.completed_at else None,
    }
