from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.session import Session as SessionModel
from app.models.task import Task

router = APIRouter(prefix="/api/sessions", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    deadline_minutes: int | None = Field(default=None, ge=1)
    consequence_type: str | None = None
    consequence_value: int | None = None


class UpdateTaskStatusRequest(BaseModel):
    status: str = Field(pattern="^(completed|failed)$")


def _load_session(db: Session, session_id: int) -> SessionModel:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_penalty_seconds(task: Task) -> int:
    if task.consequence_type not in {None, "lock_extension_seconds"}:
        return 0
    if task.consequence_value is not None and task.consequence_value > 0:
        return task.consequence_value
    return max(settings.task_overdue_default_penalty_seconds, 0)


def _apply_task_consequence(db: Session, session_obj: SessionModel, task: Task, now: datetime) -> bool:
    if task.consequence_applied_at is not None:
        return False

    penalty_seconds = _resolve_penalty_seconds(task)
    if penalty_seconds <= 0:
        return False

    if session_obj.lock_end is not None:
        session_obj.lock_end = _as_utc(session_obj.lock_end) + timedelta(seconds=penalty_seconds)
        db.add(session_obj)

    task.consequence_applied_seconds = penalty_seconds
    task.consequence_applied_at = now
    db.add(task)
    return True


def _evaluate_overdue_tasks(db: Session, session_obj: SessionModel) -> tuple[int, list[int]]:
    now = datetime.now(timezone.utc)
    changed = 0
    overdue_ids: list[int] = []
    rows = (
        db.query(Task)
        .filter(Task.session_id == session_obj.id, Task.status == "pending", Task.deadline_at.isnot(None))
        .all()
    )
    for row in rows:
        if _as_utc(row.deadline_at) > now:
            continue
        row.status = "overdue"
        if _apply_task_consequence(db=db, session_obj=session_obj, task=row, now=now):
            changed += 1
        else:
            db.add(row)
            changed += 1
        overdue_ids.append(row.id)
    if changed > 0:
        db.commit()
    return changed, overdue_ids


@router.post("/{session_id}/tasks")
def create_task(session_id: int, payload: CreateTaskRequest, db: Session = Depends(get_db)) -> dict:
    _load_session(db, session_id)

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
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {
        "task_id": task.id,
        "status": task.status,
        "title": task.title,
        "deadline_at": str(task.deadline_at) if task.deadline_at else None,
    }


@router.get("/{session_id}/tasks")
def list_tasks(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = _load_session(db, session_id)
    _evaluate_overdue_tasks(db, session_obj)
    rows = db.query(Task).filter(Task.session_id == session_id).order_by(Task.id.asc()).all()
    return {
        "session_id": session_id,
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "deadline_at": str(row.deadline_at) if row.deadline_at else None,
                "consequence_type": row.consequence_type,
                "consequence_value": row.consequence_value,
                "consequence_applied_seconds": row.consequence_applied_seconds,
                "consequence_applied_at": str(row.consequence_applied_at) if row.consequence_applied_at else None,
            }
            for row in rows
        ],
    }


@router.post("/{session_id}/tasks/evaluate-overdue")
def evaluate_overdue_tasks(session_id: int, db: Session = Depends(get_db)) -> dict:
    session_obj = _load_session(db, session_id)
    changed, overdue_ids = _evaluate_overdue_tasks(db, session_obj)
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
    db: Session = Depends(get_db),
) -> dict:
    session_obj = _load_session(db, session_id)
    task = db.query(Task).filter(Task.id == task_id, Task.session_id == session_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = payload.status
    if payload.status == "completed":
        task.completed_at = datetime.now(timezone.utc)
    if payload.status == "failed":
        _apply_task_consequence(db=db, session_obj=session_obj, task=task, now=datetime.now(timezone.utc))

    db.add(task)
    db.commit()
    db.refresh(task)
    return {
        "task_id": task.id,
        "status": task.status,
        "completed_at": str(task.completed_at) if task.completed_at else None,
    }
