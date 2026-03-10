from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.session import Session as SessionModel
from app.models.task import Task


class TaskService:
    @staticmethod
    def as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def resolve_penalty_seconds(task: Task) -> int:
        if task.consequence_type not in {None, "lock_extension_seconds"}:
            return 0
        if task.consequence_value is not None and task.consequence_value > 0:
            return task.consequence_value
        return max(settings.task_overdue_default_penalty_seconds, 0)

    @staticmethod
    def apply_task_consequence(db: Session, session_obj: SessionModel, task: Task, now: datetime) -> bool:
        if task.consequence_applied_at is not None:
            return False

        penalty_seconds = TaskService.resolve_penalty_seconds(task)
        if penalty_seconds <= 0:
            return False

        if session_obj.lock_end is not None:
            session_obj.lock_end = TaskService.as_utc(session_obj.lock_end) + timedelta(seconds=penalty_seconds)
            db.add(session_obj)

        task.consequence_applied_seconds = penalty_seconds
        task.consequence_applied_at = now
        db.add(task)
        return True

    @staticmethod
    def evaluate_overdue_tasks(db: Session, session_obj: SessionModel) -> tuple[int, list[int]]:
        now = datetime.now(timezone.utc)
        changed = 0
        overdue_ids: list[int] = []
        rows = (
            db.query(Task)
            .filter(Task.session_id == session_obj.id, Task.status == "pending", Task.deadline_at.isnot(None))
            .all()
        )
        for row in rows:
            if TaskService.as_utc(row.deadline_at) > now:
                continue
            row.status = "overdue"
            if TaskService.apply_task_consequence(db=db, session_obj=session_obj, task=row, now=now):
                changed += 1
            else:
                db.add(row)
                changed += 1
            overdue_ids.append(row.id)
        if changed > 0:
            db.commit()
        return changed, overdue_ids
