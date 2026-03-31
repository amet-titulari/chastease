from datetime import datetime, timedelta, timezone
import json

from sqlalchemy.orm import Session

from app.config import settings
from app.models.message import Message
from app.models.player_profile import PlayerProfile
from app.models.session import Session as SessionModel
from app.models.task import Task
from app.services.roleplay_progression import advance_roleplay_state_from_event, build_phase_task_key


class TaskService:
    @staticmethod
    def as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _safe_json_object(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {}

    @staticmethod
    def _psychogram_multiplier(profile: PlayerProfile | None) -> float:
        if profile is None:
            return 1.0

        level_multiplier = {
            "beginner": 1.0,
            "intermediate": 1.0,
            "advanced": 1.2,
        }.get((profile.experience_level or "").lower(), 1.0)

        reaction = TaskService._safe_json_object(profile.reaction_patterns_json)
        needs = TaskService._safe_json_object(profile.needs_json)

        reaction_multiplier = reaction.get("penalty_multiplier", 1.0)
        if not isinstance(reaction_multiplier, (int, float)):
            reaction_multiplier = 1.0

        needs_multiplier = 1.0
        if bool(needs.get("gentle_mode")):
            needs_multiplier = 0.7

        return max(0.2, float(level_multiplier) * float(reaction_multiplier) * float(needs_multiplier))

    @staticmethod
    def resolve_penalty_seconds(db: Session, session_obj: SessionModel, task: Task) -> int:
        if task.consequence_type not in {None, "lock_extension_seconds"}:
            return 0
        if task.consequence_value is not None and task.consequence_value > 0:
            return task.consequence_value

        base = max(settings.task_overdue_default_penalty_seconds, 0)

        profile = db.query(PlayerProfile).filter(PlayerProfile.id == session_obj.player_profile_id).first()
        reaction = TaskService._safe_json_object(profile.reaction_patterns_json) if profile else {}

        # Wearer-defined default takes precedence over global setting
        wearer_default = reaction.get("default_penalty_seconds")
        if isinstance(wearer_default, (int, float)) and wearer_default > 0:
            base = int(wearer_default)

        multiplier = TaskService._psychogram_multiplier(profile)
        penalty = int(round(base * multiplier))

        max_penalty = reaction.get("max_penalty_seconds")
        if isinstance(max_penalty, int) and max_penalty > 0:
            penalty = min(penalty, max_penalty)

        return max(0, penalty)

    @staticmethod
    def apply_task_consequence(db: Session, session_obj: SessionModel, task: Task, now: datetime) -> bool:
        if task.consequence_applied_at is not None:
            return False

        penalty_seconds = TaskService.resolve_penalty_seconds(db=db, session_obj=session_obj, task=task)
        if penalty_seconds <= 0:
            return False

        if session_obj.lock_end is not None:
            session_obj.lock_end = TaskService.as_utc(session_obj.lock_end) + timedelta(seconds=penalty_seconds)
            db.add(session_obj)

        task.consequence_applied_seconds = penalty_seconds
        task.consequence_applied_at = now
        db.add(task)
        db.add(
            Message(
                session_id=session_obj.id,
                role="system",
                message_type="task_penalty",
                content=(
                    f"Task-Penalty angewendet: task_id={task.id}, title='{task.title}', "
                    f"lock_extension_seconds={penalty_seconds}"
                ),
            )
        )
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
            advance_roleplay_state_from_event(
                db,
                session_obj,
                event_type="task_overdue",
                task_title=row.title,
                task_created_at=row.created_at,
                task_fingerprint=build_phase_task_key(
                    task_id=row.id,
                    title=row.title,
                    description=row.description,
                    verification_criteria=row.verification_criteria,
                ),
            )
            overdue_ids.append(row.id)
        if changed > 0:
            db.commit()
        return changed, overdue_ids
