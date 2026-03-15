from datetime import datetime, timedelta, timezone
import io
import json
import mimetypes
from pathlib import Path
import random
import re
import zipfile
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.game_module_setting import GameModuleSetting
from app.models.game_posture_template import GamePostureTemplate
from app.models.game_run import GameRun
from app.models.game_run_step import GameRunStep
from app.models.media_asset import MediaAsset
from app.models.message import Message
from app.models.session import Session as SessionModel
from app.services.games import as_public_module_payload, get_module, list_modules
from app.services.verification_analysis import analyze_verification

router = APIRouter(prefix="/api/games", tags=["games"])

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
MAX_POSTURE_IMAGE_BYTES = 8 * 1024 * 1024
POSTURE_MIN_WIDTH = 768
POSTURE_MIN_HEIGHT = 1024
POSTURE_TARGET_SIZE = (768, 1024)
DEFAULT_EASY_TARGET_MULTIPLIER = 0.85
DEFAULT_HARD_TARGET_MULTIPLIER = 1.25
DEFAULT_TARGET_RANDOMIZATION_PERCENT = 10
MAX_POSTURE_ZIP_BYTES = 64 * 1024 * 1024
MAX_RETRY_ATTEMPTS_PER_STEP_CHAIN = 2
MEDIA_CONTENT_URL_RE = re.compile(r"^/api/media/(?P<media_id>\d+)/content/?$")
SHARED_POSTURE_POOL_MODULE_KEYS = {"posture_training", "dont_move"}


class StartGameRunRequest(BaseModel):
    module_key: str = Field(default="posture_training", max_length=120)
    difficulty: str = Field(default="medium", max_length=40)
    duration_minutes: int = Field(default=20, ge=1, le=240)
    transition_seconds: int = Field(default=8, ge=0, le=60)
    initiated_by: str = Field(default="player", pattern="^(player|ai)$")
    max_misses_before_penalty: int = Field(default=3, ge=1, le=20)
    session_penalty_seconds: int = Field(default=300, ge=0, le=86400)
    easy_target_multiplier: float | None = Field(default=None, gt=0.1, le=3.0)
    hard_target_multiplier: float | None = Field(default=None, gt=0.1, le=3.0)
    target_randomization_percent: int | None = Field(default=None, ge=0, le=60)
    selected_posture_key: str | None = Field(default=None, max_length=120)
    hold_seconds: int | None = Field(default=None, ge=5, le=7200)


class ModuleSettingsUpdateRequest(BaseModel):
    easy_target_multiplier: float = Field(default=DEFAULT_EASY_TARGET_MULTIPLIER, gt=0.1, le=3.0)
    hard_target_multiplier: float = Field(default=DEFAULT_HARD_TARGET_MULTIPLIER, gt=0.1, le=3.0)
    target_randomization_percent: int = Field(default=DEFAULT_TARGET_RANDOMIZATION_PERCENT, ge=0, le=60)


class PostureTemplateCreateRequest(BaseModel):
    posture_key: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    image_url: str = Field(min_length=1, max_length=500)
    instruction: str | None = Field(default=None, max_length=2000)
    target_seconds: int = Field(default=120, ge=1, le=3600)
    sort_order: int = Field(default=0, ge=0, le=10000)
    is_active: bool = True


class PostureTemplateUpdateRequest(BaseModel):
    posture_key: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    image_url: str | None = Field(default=None, max_length=500)
    instruction: str | None = Field(default=None, max_length=2000)
    target_seconds: int | None = Field(default=None, ge=1, le=3600)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


def _load_session(db: Session, session_id: int) -> SessionModel:
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _difficulty_for(module_key: str, difficulty_key: str):
    module = get_module(module_key)
    if not module:
        return None
    for item in module.difficulties:
        if item.key == difficulty_key:
            return item
    return None


def _slug_posture_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    if not key:
        key = "posture"
    return key[:120]


def _template_payload(template: GamePostureTemplate) -> dict:
    return {
        "id": template.id,
        "module_key": template.module_key,
        "posture_key": template.posture_key,
        "title": template.title,
        "image_url": template.image_url,
        "instruction": template.instruction,
        "target_seconds": template.target_seconds,
        "sort_order": template.sort_order,
        "is_active": bool(template.is_active),
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def _posture_pool_module_key(module_key: str) -> str:
    if module_key in SHARED_POSTURE_POOL_MODULE_KEYS:
        return "posture_training"
    return module_key


def _module_postures(db: Session, module_key: str, active_only: bool = False) -> list[GamePostureTemplate]:
    pool_key = _posture_pool_module_key(module_key)
    query = (
        db.query(GamePostureTemplate)
        .filter(GamePostureTemplate.module_key == pool_key)
        .order_by(GamePostureTemplate.sort_order.asc(), GamePostureTemplate.id.asc())
    )
    if active_only:
        query = query.filter(GamePostureTemplate.is_active == True)  # noqa: E712
    return query.all()


def _resolve_media_path(storage_path: str) -> Path:
    base_dir = Path(settings.media_dir).resolve()
    target = (base_dir / storage_path).resolve()
    if base_dir not in target.parents and target != base_dir:
        raise HTTPException(status_code=500, detail="Invalid media path")
    return target


def _media_payload(asset: MediaAsset) -> dict:
    return {
        "id": asset.id,
        "media_kind": asset.media_kind,
        "content_url": f"/api/media/{asset.id}/content",
        "mime_type": asset.mime_type,
        "file_size_bytes": asset.file_size_bytes,
    }


def _process_posture_image(raw: bytes, filename: str | None, content_type: str | None = None) -> tuple[bytes, str]:
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(raw) > MAX_POSTURE_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 8 MB limit")

    mime_type = content_type or ""
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        guessed_mime, _ = mimetypes.guess_type(filename or "posture.jpg")
        mime_type = guessed_mime or mime_type
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image format")

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=415, detail="Uploaded image cannot be decoded")

    if image.width < POSTURE_MIN_WIDTH or image.height < POSTURE_MIN_HEIGHT:
        raise HTTPException(
            status_code=422,
            detail=(
                "Image resolution too small. "
                f"Minimum is {POSTURE_MIN_WIDTH}x{POSTURE_MIN_HEIGHT}px."
            ),
        )

    # Normalize all posture images to a consistent portrait format.
    normalized = ImageOps.fit(
        image.convert("RGB"),
        POSTURE_TARGET_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    out = io.BytesIO()
    normalized.save(out, format="JPEG", quality=90, optimize=True)
    processed = out.getvalue()
    if len(processed) > MAX_POSTURE_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Processed image exceeds 8 MB limit")

    original_filename = (filename or "posture").rsplit(".", 1)[0] + ".jpg"
    return processed, original_filename


def _store_posture_media(db: Session, module_key: str, image_bytes: bytes, original_filename: str) -> MediaAsset:
    storage_key = _posture_pool_module_key(module_key)
    rel_path = f"game_postures/{storage_key}/{uuid4().hex}.jpg"
    target = _resolve_media_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)

    asset = MediaAsset(
        owner_user_id=None,
        media_kind="game_posture",
        storage_path=rel_path,
        original_filename=original_filename,
        mime_type="image/jpeg",
        file_size_bytes=len(image_bytes),
        visibility="shared",
    )
    db.add(asset)
    db.flush()
    return asset


def _media_asset_from_content_url(db: Session, image_url: str) -> MediaAsset | None:
    match = MEDIA_CONTENT_URL_RE.match((image_url or "").strip())
    if not match:
        return None
    media_id = int(match.group("media_id"))
    return db.query(MediaAsset).filter(MediaAsset.id == media_id).first()


def _is_media_content_url(image_url: str) -> bool:
    return bool(MEDIA_CONTENT_URL_RE.match((image_url or "").strip()))


def _timestamp_slug(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%d_%H%M%S_%f")


def _safe_capture_suffix(filename: str | None) -> str:
    suffix = Path(filename or "capture.jpg").suffix.lower()
    if not suffix:
        return ".jpg"
    if len(suffix) > 10 or any(ch in suffix for ch in ("/", "\\", " ")):
        return ".jpg"
    return suffix


def _store_game_verification_capture(run: GameRun, image_bytes: bytes, filename: str | None) -> str:
    run_started = _as_utc(run.started_at) or datetime.now(timezone.utc)
    run_stamp = _timestamp_slug(run_started)
    capture_stamp = _timestamp_slug()
    suffix = _safe_capture_suffix(filename)

    rel_path = (
        f"verifications/games/{run.session_id}/"
        f"{run.id}-{run_stamp}_{capture_stamp}-{uuid4().hex}{suffix}"
    )
    target = _resolve_media_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    return rel_path


def _steps_for_run(db: Session, module_key: str) -> list[dict]:
    rows = _module_postures(db, module_key, active_only=True)
    if rows:
        prioritized_buckets: dict[int, list[GamePostureTemplate]] = {}
        for row in rows:
            order = int(row.sort_order or 0)
            if order <= 0:
                continue
            prioritized_buckets.setdefault(order, []).append(row)

        prioritized: list[GamePostureTemplate] = []
        for order in sorted(prioritized_buckets.keys()):
            bucket = prioritized_buckets[order]
            random.shuffle(bucket)
            prioritized.extend(bucket)

        fallback_random = [row for row in rows if int(row.sort_order or 0) <= 0]
        random.shuffle(fallback_random)
        rows = prioritized + fallback_random
        return [
            {
                "posture_key": row.posture_key,
                "posture_name": row.title,
                "posture_image_url": row.image_url,
                "instruction": row.instruction,
                "target_seconds": row.target_seconds,
            }
            for row in rows
        ]

    module = get_module(_posture_pool_module_key(module_key))
    if not module:
        return []
    return [
        {
            "posture_key": step.posture_key,
            "posture_name": step.posture_name,
            "posture_image_url": step.posture_image_url,
            "instruction": step.instruction,
            "target_seconds": step.target_seconds,
        }
        for step in module.base_steps
    ]


def _module_settings_payload(item: GameModuleSetting | None) -> dict:
    if item is None:
        return {
            "easy_target_multiplier": DEFAULT_EASY_TARGET_MULTIPLIER,
            "hard_target_multiplier": DEFAULT_HARD_TARGET_MULTIPLIER,
            "target_randomization_percent": DEFAULT_TARGET_RANDOMIZATION_PERCENT,
        }
    return {
        "easy_target_multiplier": item.easy_target_multiplier,
        "hard_target_multiplier": item.hard_target_multiplier,
        "target_randomization_percent": item.target_randomization_percent,
    }


def _load_module_settings(db: Session, module_key: str) -> GameModuleSetting | None:
    return db.query(GameModuleSetting).filter(GameModuleSetting.module_key == module_key).first()


def _resolve_effective_settings(db: Session, payload: StartGameRunRequest) -> tuple[float, float, int]:
    configured = _load_module_settings(db, payload.module_key)
    default_payload = _module_settings_payload(configured)
    easy = (
        payload.easy_target_multiplier
        if payload.easy_target_multiplier is not None
        else float(default_payload["easy_target_multiplier"])
    )
    hard = (
        payload.hard_target_multiplier
        if payload.hard_target_multiplier is not None
        else float(default_payload["hard_target_multiplier"])
    )
    randomization = (
        payload.target_randomization_percent
        if payload.target_randomization_percent is not None
        else int(default_payload["target_randomization_percent"])
    )
    return easy, hard, randomization


def _difficulty_target_multiplier(difficulty: str, easy_multiplier: float, hard_multiplier: float) -> float:
    if difficulty == "easy":
        return easy_multiplier
    if difficulty == "hard":
        return hard_multiplier
    return 1.0


def _adjust_target_seconds(base_seconds: int, multiplier: float, randomization_percent: int) -> int:
    adjusted = max(1, int(round(base_seconds * multiplier)))
    if randomization_percent <= 0:
        return adjusted

    spread = randomization_percent / 100.0
    lower = max(1, int(round(adjusted * (1.0 - spread))))
    upper = max(lower, int(round(adjusted * (1.0 + spread))))
    return random.randint(lower, upper)


def _active_step(db: Session, run_id: int) -> GameRunStep | None:
    return (
        db.query(GameRunStep)
        .filter(GameRunStep.run_id == run_id, GameRunStep.status == "pending")
        .order_by(GameRunStep.order_index.asc(), GameRunStep.id.asc())
        .first()
    )


def _retry_depth_for_step(db: Session, run_id: int, step: GameRunStep) -> int:
    depth = 0
    parent_id = step.retry_of_step_id
    while parent_id is not None:
        depth += 1
        parent = (
            db.query(GameRunStep)
            .filter(GameRunStep.id == parent_id, GameRunStep.run_id == run_id)
            .first()
        )
        if parent is None:
            break
        parent_id = parent.retry_of_step_id
    return depth


def _remaining_seconds_for_run(run: GameRun, now: datetime | None = None) -> int:
    anchor = now or datetime.now(timezone.utc)
    started = _as_utc(run.started_at) or anchor
    elapsed_seconds = max(0, int((anchor - started).total_seconds()))
    return max(0, int(run.total_duration_seconds) - elapsed_seconds)


def _load_run_summary_meta(run: GameRun) -> dict:
    if not run.summary_json:
        return {}
    try:
        parsed = json.loads(run.summary_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _append_run_check_entry(
    run: GameRun,
    *,
    step: GameRunStep,
    verification_status: str,
    analysis: str,
    capture_rel_path: str,
    sample_only: bool,
) -> None:
    meta = _load_run_summary_meta(run)
    checks = meta.get("checks")
    if not isinstance(checks, list):
        checks = []

    checks.append(
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "step_id": step.id,
            "posture_name": step.posture_name,
            "verification_status": verification_status,
            "step_status": step.status,
            "analysis": analysis,
            "violation_detected": verification_status != "confirmed",
            "violation_reason": analysis if verification_status != "confirmed" else None,
            "sample_only": bool(sample_only),
            "capture_path": capture_rel_path,
            "capture_url": f"/media/{capture_rel_path}",
        }
    )

    meta["checks"] = checks
    run.summary_json = json.dumps(meta, ensure_ascii=True)


def _finish_run_if_done(db: Session, run: GameRun) -> bool:
    now = datetime.now(timezone.utc)
    remaining_seconds = _remaining_seconds_for_run(run, now)
    pending_steps = (
        db.query(GameRunStep)
        .filter(GameRunStep.run_id == run.id, GameRunStep.status == "pending")
        .order_by(GameRunStep.order_index.asc(), GameRunStep.id.asc())
        .all()
    )
    timed_out = run.status == "active" and remaining_seconds <= 0
    if pending_steps and not timed_out:
        return False
    if run.status == "completed":
        return True

    timeout_failed = 0
    if timed_out and pending_steps:
        for item in pending_steps:
            item.status = "failed"
            item.completed_at = now
            item.last_analysis = item.last_analysis or "Nicht verifiziert: Gesamtzeit abgelaufen."
            db.add(item)
            timeout_failed += 1

    run.status = "completed"
    run.finished_at = now

    steps = db.query(GameRunStep).filter(GameRunStep.run_id == run.id).all()
    passed = sum(1 for item in steps if item.status == "passed")
    failed = sum(1 for item in steps if item.status == "failed")
    total = len(steps)
    end_reason = "time_elapsed" if timed_out else "all_steps_processed"
    existing_meta = _load_run_summary_meta(run)
    checks = existing_meta.get("checks") if isinstance(existing_meta.get("checks"), list) else []

    report = {
        "end_reason": end_reason,
        "total_steps": total,
        "passed_steps": passed,
        "failed_steps": failed,
        "timeout_failed_steps": timeout_failed,
        "miss_count": run.miss_count,
        "retry_extension_seconds": run.retry_extension_seconds,
        "session_penalty_applied": bool(run.session_penalty_applied),
        "scheduled_duration_seconds": int(run.total_duration_seconds),
        "checks": checks,
    }
    run.summary_json = json.dumps(report, ensure_ascii=True)

    db.add(
        Message(
            session_id=run.session_id,
            role="system",
            message_type="game_report",
            content=(
                f"Spielbericht {run.module_key}: "
                f"reason={end_reason}, total={total}, passed={passed}, failed={failed}, "
                f"timeout_failed={timeout_failed}, misses={run.miss_count}, "
                f"retry_extension_seconds={run.retry_extension_seconds}, "
                f"session_penalty_applied={run.session_penalty_applied}"
            ),
        )
    )
    db.add(run)
    return True


def _run_payload(db: Session, run: GameRun) -> dict:
    now = datetime.now(timezone.utc)
    started = _as_utc(run.started_at) or now
    remaining_seconds = _remaining_seconds_for_run(run, now)

    current_step = _active_step(db, run.id)
    summary_payload = None
    if run.summary_json:
        try:
            summary_payload = json.loads(run.summary_json)
        except json.JSONDecodeError:
            summary_payload = {"raw": run.summary_json}

    current_step_payload = None
    if current_step:
        transition_seconds = max(0, int(run.transition_seconds or 0))
        max_hold_seconds = max(0, remaining_seconds - transition_seconds)
        effective_target_seconds = min(int(current_step.target_seconds), max_hold_seconds)
        current_step_payload = {
            "id": current_step.id,
            "order_index": current_step.order_index,
            "posture_key": current_step.posture_key,
            "posture_name": current_step.posture_name,
            "posture_image_url": current_step.posture_image_url,
            "instruction": current_step.instruction,
            "target_seconds": effective_target_seconds,
            "raw_target_seconds": current_step.target_seconds,
            "verification_count": current_step.verification_count,
        }

    return {
        "id": run.id,
        "session_id": run.session_id,
        "module_key": run.module_key,
        "difficulty": run.difficulty_key,
        "status": run.status,
        "initiated_by": run.initiated_by,
        "max_misses_before_penalty": run.max_misses_before_penalty,
        "miss_count": run.miss_count,
        "transition_seconds": run.transition_seconds,
        "session_penalty_seconds": run.session_penalty_seconds,
        "session_penalty_applied": bool(run.session_penalty_applied),
        "total_duration_seconds": run.total_duration_seconds,
        "retry_extension_seconds": run.retry_extension_seconds,
        "remaining_seconds": remaining_seconds,
        "started_at": started.isoformat(),
        "finished_at": _as_utc(run.finished_at).isoformat() if run.finished_at else None,
        "summary": summary_payload,
        "current_step": current_step_payload,
    }


@router.get("/modules")
def list_game_modules() -> dict:
    return {"items": [as_public_module_payload(module) for module in list_modules()]}


@router.get("/modules/{module_key}")
def get_game_module(module_key: str) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    return as_public_module_payload(module)


@router.get("/modules/{module_key}/settings")
def get_module_settings(module_key: str, db: Session = Depends(get_db)) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    item = _load_module_settings(db, module_key)
    return _module_settings_payload(item)


@router.put("/modules/{module_key}/settings")
def update_module_settings(
    module_key: str,
    payload: ModuleSettingsUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    item = _load_module_settings(db, module_key)
    if item is None:
        item = GameModuleSetting(module_key=module_key)
    item.easy_target_multiplier = payload.easy_target_multiplier
    item.hard_target_multiplier = payload.hard_target_multiplier
    item.target_randomization_percent = payload.target_randomization_percent
    db.add(item)
    db.commit()
    db.refresh(item)
    return _module_settings_payload(item)


@router.get("/modules/{module_key}/postures")
def list_module_postures(module_key: str, db: Session = Depends(get_db)) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    rows = _module_postures(db, module_key, active_only=False)
    return {"items": [_template_payload(row) for row in rows]}


@router.post("/modules/{module_key}/postures/upload-image")
async def upload_module_posture_image(
    module_key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    raw = await file.read()
    processed, original_filename = _process_posture_image(raw, file.filename, file.content_type)
    asset = _store_posture_media(db, module_key, processed, original_filename)
    db.commit()
    db.refresh(asset)
    return _media_payload(asset)


@router.get("/modules/{module_key}/postures/export")
def export_module_postures_zip(module_key: str, db: Session = Depends(get_db)):
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    postures = _module_postures(db, module_key, active_only=False)
    archive_io = io.BytesIO()

    with zipfile.ZipFile(archive_io, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest_items: list[dict] = []
        for posture in postures:
            item = {
                "posture_key": posture.posture_key,
                "title": posture.title,
                "instruction": posture.instruction,
                "target_seconds": posture.target_seconds,
                "sort_order": posture.sort_order,
                "is_active": bool(posture.is_active),
            }

            asset = _media_asset_from_content_url(db, posture.image_url)
            if asset:
                path = _resolve_media_path(asset.storage_path)
                if path.exists() and path.is_file():
                    safe_slug = _slug_posture_key(posture.title or posture.posture_key)
                    image_name = f"images/{posture.id}_{safe_slug}.jpg"
                    archive.writestr(image_name, path.read_bytes())
                    item["image_file"] = image_name
                else:
                    item["image_url"] = posture.image_url
            else:
                item["image_url"] = posture.image_url

            manifest_items.append(item)

        manifest = {
            "format": "chastease-postures-v1",
            "module_key": module_key,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "postures": manifest_items,
        }
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True, indent=2))

    archive_io.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"postures_{module_key}_{stamp}.zip"
    return StreamingResponse(
        archive_io,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/modules/{module_key}/postures/import-zip")
async def import_module_postures_zip(
    module_key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    raw_zip = await file.read()
    if not raw_zip:
        raise HTTPException(status_code=422, detail="Uploaded ZIP is empty")
    if len(raw_zip) > MAX_POSTURE_ZIP_BYTES:
        raise HTTPException(status_code=413, detail="ZIP exceeds 64 MB limit")
    if not zipfile.is_zipfile(io.BytesIO(raw_zip)):
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid ZIP archive")

    archive = zipfile.ZipFile(io.BytesIO(raw_zip), mode="r")
    if "manifest.json" not in archive.namelist():
        raise HTTPException(status_code=422, detail="ZIP manifest.json is missing")

    try:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=422, detail="manifest.json is invalid")

    items = manifest.get("postures")
    if not isinstance(items, list):
        raise HTTPException(status_code=422, detail="manifest.json must contain a postures array")

    pool_key = _posture_pool_module_key(module_key)

    replaced = (
        db.query(GamePostureTemplate)
        .filter(GamePostureTemplate.module_key == pool_key)
        .count()
    )

    try:
        (
            db.query(GamePostureTemplate)
            .filter(GamePostureTemplate.module_key == pool_key)
            .delete(synchronize_session=False)
        )

        imported = 0
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise HTTPException(status_code=422, detail=f"Posture entry #{idx} is invalid")

            title = str(item.get("title") or "").strip()
            if not title:
                raise HTTPException(status_code=422, detail=f"Posture entry #{idx} has no title")

            image_file = str(item.get("image_file") or "").strip()
            image_url = str(item.get("image_url") or "").strip()
            resolved_image_url = ""

            if image_file:
                try:
                    image_raw = archive.read(image_file)
                except KeyError:
                    raise HTTPException(status_code=422, detail=f"Image file missing in ZIP: {image_file}")
                processed, original_filename = _process_posture_image(
                    image_raw,
                    Path(image_file).name,
                    None,
                )
                asset = _store_posture_media(db, module_key, processed, original_filename)
                resolved_image_url = f"/api/media/{asset.id}/content"
            elif image_url:
                if _is_media_content_url(image_url):
                    existing_asset = _media_asset_from_content_url(db, image_url)
                    if existing_asset is None:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                "ZIP enthaelt lokale Bild-URL ohne eingebettete Bilddatei. "
                                "Bitte erneut exportieren und dieselbe ZIP verwenden."
                            ),
                        )
                resolved_image_url = image_url
            else:
                raise HTTPException(status_code=422, detail=f"Posture entry #{idx} has no image")

            raw_target = item.get("target_seconds", 120)
            raw_order = item.get("sort_order", 0)
            target_seconds = min(3600, max(1, int(raw_target)))
            sort_order = min(10000, max(0, int(raw_order)))

            posture_key = str(item.get("posture_key") or "").strip() or _slug_posture_key(title)
            instruction = str(item.get("instruction") or "").strip() or None
            is_active = bool(item.get("is_active", True))

            db.add(
                GamePostureTemplate(
                    module_key=pool_key,
                    posture_key=posture_key[:120],
                    title=title,
                    image_url=resolved_image_url,
                    instruction=instruction,
                    target_seconds=target_seconds,
                    sort_order=sort_order,
                    is_active=is_active,
                )
            )
            imported += 1

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except ValueError:
        db.rollback()
        raise HTTPException(status_code=422, detail="ZIP contains invalid numeric posture fields")

    return {"imported": imported, "replaced": replaced}


@router.post("/modules/{module_key}/postures")
def create_module_posture(
    module_key: str,
    payload: PostureTemplateCreateRequest,
    db: Session = Depends(get_db),
) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    posture_key = (payload.posture_key or "").strip() or _slug_posture_key(payload.title)
    image_url = payload.image_url.strip()
    if not image_url:
        raise HTTPException(status_code=422, detail="image_url is required")

    pool_key = _posture_pool_module_key(module_key)

    template = GamePostureTemplate(
        module_key=pool_key,
        posture_key=posture_key[:120],
        title=payload.title.strip(),
        image_url=image_url,
        instruction=(payload.instruction or "").strip() or None,
        target_seconds=payload.target_seconds,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_payload(template)


@router.put("/modules/{module_key}/postures/{posture_id}")
def update_module_posture(
    module_key: str,
    posture_id: int,
    payload: PostureTemplateUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    pool_key = _posture_pool_module_key(module_key)

    template = (
        db.query(GamePostureTemplate)
        .filter(GamePostureTemplate.id == posture_id, GamePostureTemplate.module_key == pool_key)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Posture not found")

    if payload.posture_key is not None:
        template.posture_key = payload.posture_key.strip()[:120] or template.posture_key
    if payload.title is not None:
        template.title = payload.title.strip()
    if payload.image_url is not None:
        next_image = payload.image_url.strip()
        if not next_image:
            raise HTTPException(status_code=422, detail="image_url cannot be empty")
        template.image_url = next_image
    if payload.instruction is not None:
        template.instruction = payload.instruction.strip() or None
    if payload.target_seconds is not None:
        template.target_seconds = payload.target_seconds
    if payload.sort_order is not None:
        template.sort_order = payload.sort_order
    if payload.is_active is not None:
        template.is_active = payload.is_active

    if not template.image_url:
        raise HTTPException(status_code=422, detail="image_url is required")

    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_payload(template)


@router.delete("/modules/{module_key}/postures/{posture_id}")
def delete_module_posture(module_key: str, posture_id: int, db: Session = Depends(get_db)) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    pool_key = _posture_pool_module_key(module_key)

    template = (
        db.query(GamePostureTemplate)
        .filter(GamePostureTemplate.id == posture_id, GamePostureTemplate.module_key == pool_key)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Posture not found")
    db.delete(template)
    db.commit()
    return {"deleted": posture_id}


@router.post("/sessions/{session_id}/runs/start")
def start_game_run(session_id: int, payload: StartGameRunRequest, db: Session = Depends(get_db)) -> dict:
    _load_session(db, session_id)
    module = get_module(payload.module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    difficulty = _difficulty_for(payload.module_key, payload.difficulty)
    if not difficulty:
        raise HTTPException(status_code=409, detail="Difficulty not supported for this module")

    run = GameRun(
        session_id=session_id,
        module_key=module.key,
        difficulty_key=difficulty.key,
        initiated_by=payload.initiated_by,
        status="active",
        total_duration_seconds=payload.duration_minutes * 60,
        retry_extension_seconds=0,
        transition_seconds=payload.transition_seconds,
        max_misses_before_penalty=payload.max_misses_before_penalty,
        miss_count=0,
        session_penalty_seconds=payload.session_penalty_seconds,
        session_penalty_applied=False,
    )
    db.add(run)
    db.flush()

    available_steps = _steps_for_run(db, module.key)
    if not available_steps:
        raise HTTPException(status_code=409, detail="No postures configured for this module")

    selected_steps = list(available_steps)
    if module.key == "dont_move":
        if payload.selected_posture_key:
            selected_steps = [
                step
                for step in available_steps
                if (step.get("posture_key") or "") == payload.selected_posture_key
            ]
            if not selected_steps:
                raise HTTPException(status_code=422, detail="Selected posture is not available")
        else:
            selected_steps = [available_steps[0]]

        if payload.hold_seconds is not None:
            chosen = dict(selected_steps[0])
            chosen["target_seconds"] = int(payload.hold_seconds)
            selected_steps = [chosen]
        else:
            selected_steps = [selected_steps[0]]

    easy_multiplier, hard_multiplier, randomization_percent = _resolve_effective_settings(db, payload)
    target_multiplier = _difficulty_target_multiplier(payload.difficulty, easy_multiplier, hard_multiplier)

    if module.key == "dont_move":
        target_multiplier = 1.0
        randomization_percent = 0

    for idx, step in enumerate(selected_steps):
        base_target_seconds = max(1, int(step["target_seconds"] or 120))
        target_seconds = _adjust_target_seconds(
            base_seconds=base_target_seconds,
            multiplier=target_multiplier,
            randomization_percent=randomization_percent,
        )
        db.add(
            GameRunStep(
                run_id=run.id,
                order_index=idx + 1,
                posture_key=step["posture_key"],
                posture_name=step["posture_name"],
                posture_image_url=step["posture_image_url"],
                instruction=step["instruction"],
                target_seconds=target_seconds,
                status="pending",
                verification_count=0,
            )
        )

    db.add(
        Message(
            session_id=session_id,
            role="system",
            message_type="game_started",
            content=(
                f"Spiel gestartet: {module.title} | difficulty={difficulty.label} | "
                f"duration_minutes={payload.duration_minutes} | max_misses={payload.max_misses_before_penalty} | "
                f"target_multiplier={target_multiplier} | target_randomization_percent={randomization_percent}"
            ),
        )
    )

    db.commit()
    db.refresh(run)
    return _run_payload(db, run)


@router.get("/runs/{run_id}")
def get_game_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.query(GameRun).filter(GameRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Game run not found")
    _finish_run_if_done(db, run)
    db.commit()
    db.refresh(run)
    payload = _run_payload(db, run)
    payload["steps"] = [
        {
            "id": row.id,
            "order_index": row.order_index,
            "posture_name": row.posture_name,
            "posture_image_url": row.posture_image_url,
            "instruction": row.instruction,
            "target_seconds": row.target_seconds,
            "status": row.status,
            "verification_count": row.verification_count,
            "retry_of_step_id": row.retry_of_step_id,
            "last_analysis": row.last_analysis,
        }
        for row in db.query(GameRunStep)
        .filter(GameRunStep.run_id == run.id)
        .order_by(GameRunStep.order_index.asc(), GameRunStep.id.asc())
        .all()
    ]
    return payload


@router.post("/runs/{run_id}/steps/{step_id}/verify")
async def verify_game_step(
    run_id: int,
    step_id: int,
    file: UploadFile = File(...),
    observed_posture: str | None = Form(default=None),
    sample_only: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> dict:
    run = db.query(GameRun).filter(GameRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Game run not found")
    if run.status != "active":
        raise HTTPException(status_code=409, detail="Game run is not active")

    step = (
        db.query(GameRunStep)
        .filter(GameRunStep.id == step_id, GameRunStep.run_id == run_id)
        .first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Game step not found")
    if step.status != "pending":
        raise HTTPException(status_code=409, detail="Game step is not pending")

    data = await file.read()
    capture_rel_path = _store_game_verification_capture(run, data, file.filename)
    difficulty = _difficulty_for(run.module_key, run.difficulty_key)
    if difficulty is None:
        raise HTTPException(status_code=409, detail="Difficulty profile missing")

    status, analysis = analyze_verification(
        image_bytes=data,
        filename=file.filename or "capture.jpg",
        requested_seal_number=None,
        observed_seal_number=observed_posture,
        verification_criteria=(
            (
                "Aufgabe: strenge Bildpruefung fuer eine konkrete Pose. "
                f"Soll-Pose: '{step.posture_name}'. "
                f"Soll-Kriterien: {(step.instruction or 'Keine Zusatzkriterien hinterlegt.').strip()} "
                "Bewerte 'confirmed' NUR wenn die Pose klar sichtbar ist und mit Soll-Pose plus Kriterien uebereinstimmt. "
                "Wenn Koerperhaltung, Ausrichtung, Kamerawinkel oder Bildqualitaet keine sichere Zuordnung erlauben: 'suspicious'. "
                "Bei Teiltreffern oder Unsicherheit niemals 'confirmed'."
            )
        ),
        allow_heuristic_fallback=False,
    )

    step.verification_count += 1
    step.last_analysis = analysis
    now = datetime.now(timezone.utc)

    def _handle_failed_step_with_retry_policy() -> None:
        nonlocal run, step

        run.miss_count += 1
        disable_retry_for_module = run.module_key == "dont_move"
        retry_depth = _retry_depth_for_step(db, run.id, step)
        can_append_retry = (not disable_retry_for_module) and (retry_depth < MAX_RETRY_ATTEMPTS_PER_STEP_CHAIN)

        if can_append_retry:
            run.retry_extension_seconds += difficulty.retry_extension_seconds
            run.total_duration_seconds += difficulty.retry_extension_seconds

            last_order = (
                db.query(GameRunStep)
                .filter(GameRunStep.run_id == run.id)
                .order_by(GameRunStep.order_index.desc())
                .first()
            )
            next_order = (last_order.order_index if last_order else 0) + 1
            db.add(
                GameRunStep(
                    run_id=run.id,
                    order_index=next_order,
                    posture_key=step.posture_key,
                    posture_name=step.posture_name,
                    posture_image_url=step.posture_image_url,
                    instruction=step.instruction,
                    target_seconds=step.target_seconds,
                    status="pending",
                    retry_of_step_id=step.id,
                )
            )

            db.add(
                Message(
                    session_id=run.session_id,
                    role="system",
                    message_type="game_step_fail",
                    content=(
                        f"Posture nicht bestaetigt: {step.posture_name}. "
                        f"Retry angehaengt ({retry_depth + 1}/{MAX_RETRY_ATTEMPTS_PER_STEP_CHAIN}), "
                        f"Gesamtzeit +{difficulty.retry_extension_seconds}s."
                    ),
                )
            )
        else:
            db.add(
                Message(
                    session_id=run.session_id,
                    role="system",
                    message_type="game_step_fail",
                    content=(
                        f"Posture nicht bestaetigt: {step.posture_name}. "
                        f"Retry-Limit erreicht ({MAX_RETRY_ATTEMPTS_PER_STEP_CHAIN}), kein weiterer Versuch angehaengt."
                    ),
                )
            )

        if (
            run.session_penalty_seconds > 0
            and not run.session_penalty_applied
            and run.miss_count >= run.max_misses_before_penalty
        ):
            session_obj = _load_session(db, run.session_id)
            current_lock_end = _as_utc(session_obj.lock_end) or now
            session_obj.lock_end = current_lock_end + timedelta(seconds=run.session_penalty_seconds)
            run.session_penalty_applied = True
            db.add(session_obj)
            db.add(
                Message(
                    session_id=run.session_id,
                    role="system",
                    message_type="game_penalty",
                    content=(
                        "Session-Penalty ausgeloest durch zu viele Verfehlungen: "
                        f"+{run.session_penalty_seconds}s"
                    ),
                )
            )

    if sample_only:
        if status == "confirmed":
            db.add(
                Message(
                    session_id=run.session_id,
                    role="system",
                    message_type="game_step_sample_pass",
                    content=f"Stichprobe bestanden: {step.posture_name}",
                )
            )
        else:
            step.status = "failed"
            step.completed_at = now
            _handle_failed_step_with_retry_policy()

            db.add(
                Message(
                    session_id=run.session_id,
                    role="system",
                    message_type="game_step_sample_fail",
                    content=f"Stichprobe fehlgeschlagen: {step.posture_name}",
                )
            )
    elif status == "confirmed":
        step.status = "passed"
        step.completed_at = now
        db.add(
            Message(
                session_id=run.session_id,
                role="system",
                message_type="game_step_pass",
                content=f"Posture bestaetigt: {step.posture_name}",
            )
        )
    else:
        step.status = "failed"
        step.completed_at = now
        _handle_failed_step_with_retry_policy()

    _append_run_check_entry(
        run,
        step=step,
        verification_status=status,
        analysis=analysis,
        capture_rel_path=capture_rel_path,
        sample_only=sample_only,
    )

    db.add(step)
    db.add(run)
    _finish_run_if_done(db, run)
    db.commit()
    db.refresh(run)
    db.refresh(step)
    return {
        "run": _run_payload(db, run),
        "step": {
            "id": step.id,
            "status": step.status,
            "verification_count": step.verification_count,
            "verification_status": status,
            "analysis": step.last_analysis,
            "capture_path": capture_rel_path,
            "capture_url": f"/media/{capture_rel_path}",
            "sample_only": sample_only,
            "finalized": step.status != "pending",
        },
    }
