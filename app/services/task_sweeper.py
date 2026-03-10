from app.database import SessionLocal
from app.models.session import Session as SessionModel
from app.services.task_service import TaskService


def sweep_overdue_tasks_for_active_sessions() -> dict:
    with SessionLocal() as db:
        sessions = db.query(SessionModel).filter(SessionModel.status == "active").all()
        changed_total = 0
        affected_sessions = 0

        for session_obj in sessions:
            changed, _ = TaskService.evaluate_overdue_tasks(db=db, session_obj=session_obj)
            if changed > 0:
                affected_sessions += 1
                changed_total += changed

        return {
            "scanned_sessions": len(sessions),
            "affected_sessions": affected_sessions,
            "changed_tasks": changed_total,
        }
