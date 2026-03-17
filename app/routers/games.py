from datetime import datetime, timedelta, timezone
import io
import json
import logging
import mimetypes
from pathlib import Path
import random
import re
import sys
import traceback
import zipfile
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.game_module_setting import GameModuleSetting
from app.models.game_posture_module_assignment import GamePostureModuleAssignment
from app.models.game_posture_template import GamePostureTemplate
from app.models.game_run import GameRun
from app.models.game_run_step import GameRunStep
from app.models.media_asset import MediaAsset
from app.models.message import Message
from app.models.session import Session as SessionModel
from app.security import require_admin_session_user
from app.services.games import as_public_module_payload, get_module, list_modules
from app.services.image_stamp import stamp_verification_timestamp
from app.services.audit_logger import audit_log
from app.services.pose_similarity import extract_reference_landmarks_json, pose_similarity_available, score_against_reference
from app.services.verification_analysis import analyze_verification, generate_game_run_summary

router = APIRouter(prefix="/api/games", tags=["games"])
logger = logging.getLogger(__name__)

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
DEFAULT_EASY_TARGET_MULTIPLIER = 0.75
DEFAULT_HARD_TARGET_MULTIPLIER = 1.5
DEFAULT_TARGET_RANDOMIZATION_PERCENT = 10
DEFAULT_STRICT_START_COUNTDOWN_SECONDS = 5
GLOBAL_GAME_SETTINGS_KEY = "__global__"
POSE_SIMILARITY_THRESHOLD_BY_DIFFICULTY = {
    "easy": 62.0,
    "medium": 74.0,
    "hard": 84.0,
}
DEFAULT_MOVEMENT_THRESHOLDS_BY_MODULE = {
    "dont_move": {
        "easy": {"pose_deviation": 0.40, "stillness": 0.0400},
        "medium": {"pose_deviation": 0.35, "stillness": 0.0300},
        "hard": {"pose_deviation": 0.225, "stillness": 0.0200},
    },
    "tiptoeing": {
        # Tiptoeing uses these fields as mask color thresholds:
        # - pose_deviation => black threshold (0..1)
        # - stillness => green minimum channel threshold (0..1)
        "easy": {"pose_deviation": 0.14, "stillness": 0.22},
        "medium": {"pose_deviation": 0.18, "stillness": 0.26},
        "hard": {"pose_deviation": 0.22, "stillness": 0.30},
    },
}
MAX_POSTURE_ZIP_BYTES = 64 * 1024 * 1024
MAX_RETRY_ATTEMPTS_PER_STEP_CHAIN = 2
MEDIA_CONTENT_URL_RE = re.compile(r"^/api/media/(?P<media_id>\d+)/content/?$")
SHARED_POSTURE_POOL_MODULE_KEYS = {"posture_training", "dont_move"}
EMPTY_ALLOWED_MODULE_SENTINEL = "__none__"
SINGLE_POSE_STRICT_MODULE_KEYS = {"dont_move", "tiptoeing"}


def _is_single_pose_strict_module(module_key: str) -> bool:
    return module_key in SINGLE_POSE_STRICT_MODULE_KEYS


class StartGameRunRequest(BaseModel):
    module_key: str = Field(default="posture_training", max_length=120)
    difficulty: str = Field(default="medium", max_length=40)
    duration_minutes: int = Field(default=20, ge=1, le=240)
    transition_seconds: int = Field(default=8, ge=0, le=60)
    start_countdown_seconds: int | None = Field(default=None, ge=0, le=60)
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
    start_countdown_seconds: int = Field(default=DEFAULT_STRICT_START_COUNTDOWN_SECONDS, ge=0, le=60)
    movement_easy_pose_deviation: float = Field(default=0.40, ge=0.01, le=1.0)
    movement_easy_stillness: float = Field(default=0.040, ge=0.0005, le=1.0)
    movement_medium_pose_deviation: float = Field(default=0.35, ge=0.01, le=1.0)
    movement_medium_stillness: float = Field(default=0.030, ge=0.0005, le=1.0)
    movement_hard_pose_deviation: float = Field(default=0.225, ge=0.01, le=1.0)
    movement_hard_stillness: float = Field(default=0.020, ge=0.0005, le=1.0)
    pose_similarity_min_score_easy: float = Field(default=62.0, ge=0.0, le=100.0)
    pose_similarity_min_score_medium: float = Field(default=74.0, ge=0.0, le=100.0)
    pose_similarity_min_score_hard: float = Field(default=84.0, ge=0.0, le=100.0)


class GlobalGameSettingsUpdateRequest(BaseModel):
    easy_target_multiplier: float = Field(default=DEFAULT_EASY_TARGET_MULTIPLIER, gt=0.1, le=3.0)
    hard_target_multiplier: float = Field(default=DEFAULT_HARD_TARGET_MULTIPLIER, gt=0.1, le=3.0)
    target_randomization_percent: int = Field(default=DEFAULT_TARGET_RANDOMIZATION_PERCENT, ge=0, le=60)
    start_countdown_seconds: int = Field(default=DEFAULT_STRICT_START_COUNTDOWN_SECONDS, ge=0, le=60)


class PostureTemplateCreateRequest(BaseModel):
    posture_key: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    image_url: str = Field(min_length=1, max_length=500)
    instruction: str | None = Field(default=None, max_length=2000)
    target_seconds: int = Field(default=120, ge=1, le=3600)
    sort_order: int = Field(default=0, ge=0, le=10000)
    is_active: bool = True
    allowed_module_keys: list[str] | None = None


class PostureTemplateUpdateRequest(BaseModel):
    posture_key: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    image_url: str | None = Field(default=None, max_length=500)
    instruction: str | None = Field(default=None, max_length=2000)
    target_seconds: int | None = Field(default=None, ge=1, le=3600)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None
    allowed_module_keys: list[str] | None = None


class PostureMatrixItemUpdateRequest(BaseModel):
    posture_id: int = Field(ge=1)
    allowed_module_keys: list[str] = Field(default_factory=list)


class PostureMatrixBulkUpdateRequest(BaseModel):
    items: list[PostureMatrixItemUpdateRequest] = Field(default_factory=list)


class PostureReferencePoseUpdateRequest(BaseModel):
    enabled: bool = True
    refresh: bool = False


class PostureReferencePoseManualUpdateRequest(BaseModel):
    reference_landmarks_json: str = Field(min_length=2, max_length=200000)


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


def _template_payload(template: GamePostureTemplate, allowed_module_keys: list[str] | None = None) -> dict:
    pool_key = _posture_pool_module_key(template.module_key)
    if allowed_module_keys is None:
        effective_allowed = _default_allowed_module_keys_for_pool(pool_key)
    else:
        effective_allowed = allowed_module_keys
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
        "reference_pose_available": bool(template.reference_landmarks_json),
        "reference_landmarks_json": template.reference_landmarks_json,
        "allowed_module_keys": sorted({str(item) for item in effective_allowed if str(item).strip()}),
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def _posture_pool_module_key(module_key: str) -> str:
    if module_key in SHARED_POSTURE_POOL_MODULE_KEYS:
        return "posture_training"
    return module_key


def _default_allowed_module_keys_for_pool(module_key: str) -> list[str]:
    if module_key == "posture_training":
        return sorted(SHARED_POSTURE_POOL_MODULE_KEYS)
    return [module_key]


def _normalize_allowed_module_keys(
    module_keys: list[str] | None,
    pool_key: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if module_keys is None:
        return _default_allowed_module_keys_for_pool(pool_key)

    known_module_keys = {module.key for module in list_modules()}
    normalized: list[str] = []
    for value in module_keys:
        key = str(value or "").strip()
        if not key or key in normalized or key not in known_module_keys:
            continue
        normalized.append(key)

    if not normalized:
        if allow_empty:
            return []
        return _default_allowed_module_keys_for_pool(pool_key)
    return normalized


def _load_allowed_module_map(db: Session, posture_ids: list[int]) -> dict[int, set[str]]:
    if not posture_ids:
        return {}

    rows = (
        db.query(GamePostureModuleAssignment)
        .filter(GamePostureModuleAssignment.posture_template_id.in_(posture_ids))
        .all()
    )

    payload: dict[int, set[str]] = {}
    for row in rows:
        posture_id = int(row.posture_template_id)
        payload.setdefault(posture_id, set())
        module_key = str(row.module_key)
        if module_key == EMPTY_ALLOWED_MODULE_SENTINEL:
            continue
        payload[posture_id].add(module_key)
    return payload


def _resolved_allowed_module_keys(
    template: GamePostureTemplate,
    allowed_map: dict[int, set[str]],
) -> list[str]:
    allowed = allowed_map.get(int(template.id))
    if allowed is None:
        return _default_allowed_module_keys_for_pool(_posture_pool_module_key(template.module_key))
    return sorted(allowed)


def _set_allowed_module_keys(db: Session, posture_template_id: int, module_keys: list[str]) -> None:
    (
        db.query(GamePostureModuleAssignment)
        .filter(GamePostureModuleAssignment.posture_template_id == posture_template_id)
        .delete(synchronize_session=False)
    )
    if not module_keys:
        db.add(
            GamePostureModuleAssignment(
                posture_template_id=posture_template_id,
                module_key=EMPTY_ALLOWED_MODULE_SENTINEL,
            )
        )
        return
    for key in module_keys:
        db.add(
            GamePostureModuleAssignment(
                posture_template_id=posture_template_id,
                module_key=key,
            )
        )


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

    # Normalize all posture images to a consistent portrait format.
    # Smaller images are upscaled to keep admin UX simple and predictable.
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


def _try_load_posture_image_bytes_from_url(db: Session, image_url: str) -> bytes | None:
    asset = _media_asset_from_content_url(db, image_url)
    if not asset:
        return None
    try:
        media_path = _resolve_media_path(asset.storage_path)
    except HTTPException:
        return None
    if not media_path.exists() or not media_path.is_file():
        return None
    try:
        return media_path.read_bytes()
    except OSError:
        return None


def _refresh_reference_landmarks(template: GamePostureTemplate, image_bytes: bytes | None) -> None:
    if not image_bytes:
        logger.debug("_refresh_reference_landmarks: no image bytes for posture_key=%s", getattr(template, "posture_key", "?"))
        template.reference_landmarks_json = None
        template.reference_landmarks_detected_at = None
        return
    reference_json = extract_reference_landmarks_json(image_bytes)
    if reference_json is None:
        logger.info(
            "_refresh_reference_landmarks: detection returned no landmarks for posture_key=%s (image %d bytes)",
            getattr(template, "posture_key", "?"),
            len(image_bytes),
        )
        template.reference_landmarks_json = None
        template.reference_landmarks_detected_at = None
        return
    logger.info("_refresh_reference_landmarks: landmarks detected for posture_key=%s", getattr(template, "posture_key", "?"))
    template.reference_landmarks_json = reference_json
    template.reference_landmarks_detected_at = datetime.now(timezone.utc)


def _lookup_posture_template_for_step(db: Session, run: GameRun, step: GameRunStep) -> GamePostureTemplate | None:
    pool_key = _posture_pool_module_key(run.module_key)
    return (
        db.query(GamePostureTemplate)
        .filter(
            GamePostureTemplate.module_key == pool_key,
            GamePostureTemplate.posture_key == step.posture_key,
        )
        .order_by(GamePostureTemplate.id.desc())
        .first()
    )


def _evaluate_pose_similarity_for_step(
    db: Session,
    run: GameRun,
    step: GameRunStep,
    image_bytes: bytes,
) -> tuple[str, str, dict | None]:
    if run.module_key != "posture_training":
        return "skipped", "pose_similarity_not_applicable", None
    if not pose_similarity_available():
        return "skipped", "pose_runtime_unavailable", None

    template = _lookup_posture_template_for_step(db, run, step)
    if template is None:
        return "skipped", "reference_template_not_found", None
    if not template.reference_landmarks_json:
        return "skipped", "reference_pose_not_available", None

    scored = score_against_reference(image_bytes=image_bytes, reference_landmarks_json=template.reference_landmarks_json)
    if scored is None:
        return "skipped", "pose_not_detected", None

    difficulty_key = str(run.difficulty_key or "medium").lower()
    module_settings = _module_settings_payload(_load_module_settings(db, run.module_key), run.module_key)
    threshold = float(
        {
            "easy": module_settings.get("pose_similarity_min_score_easy", 62.0),
            "medium": module_settings.get("pose_similarity_min_score_medium", 74.0),
            "hard": module_settings.get("pose_similarity_min_score_hard", 84.0),
        }.get(difficulty_key, module_settings.get("pose_similarity_min_score_medium", 74.0))
    )
    score = float(scored.get("score", 0.0))
    if score >= threshold:
        return "confirmed", f"Pose-Score {score:.1f}/100 (min {threshold:.1f})", {
            "score": score,
            "threshold": threshold,
            "difficulty": difficulty_key,
            **scored,
        }
    return "suspicious", f"Pose-Score {score:.1f}/100 (min {threshold:.1f})", {
        "score": score,
        "threshold": threshold,
        "difficulty": difficulty_key,
        **scored,
    }


def _is_media_content_url(image_url: str) -> bool:
    return bool(MEDIA_CONTENT_URL_RE.match((image_url or "").strip()))


def _timestamp_slug(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%d-%H%M")


def _safe_capture_suffix(filename: str | None) -> str:
    suffix = Path(filename or "capture.jpg").suffix.lower()
    if not suffix:
        return ".jpg"
    if len(suffix) > 10 or any(ch in suffix for ch in ("/", "\\", " ")):
        return ".jpg"
    return suffix


def _store_game_verification_capture(run: GameRun, image_bytes: bytes, filename: str | None, run_number: int) -> str:
    capture_stamp = _timestamp_slug()
    suffix = _safe_capture_suffix(filename)

    rel_path = (
        f"verifications/games/{run.session_id}/"
        f"session{run.session_id}-game{run.id}-run{max(1, int(run_number))}-{capture_stamp}{suffix}"
    )
    target = _resolve_media_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(stamp_verification_timestamp(image_bytes))
    return rel_path


def _annotate_movement_capture(
    image_bytes: bytes,
    *,
    marker_x: float | None,
    marker_y: float | None,
    marker_label: str | None = None,
    marker_strength: float | None = None,
) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            image = ImageOps.exif_transpose(raw_img).convert("RGB")
    except Exception:
        return image_bytes

    width, height = image.size
    if width <= 0 or height <= 0:
        return image_bytes

    mx = 0.5 if marker_x is None else max(0.0, min(1.0, float(marker_x)))
    my = 0.72 if marker_y is None else max(0.0, min(1.0, float(marker_y)))
    px = int(round(mx * width))
    py = int(round(my * height))

    draw = ImageDraw.Draw(image, "RGBA")
    strength = max(0.0, float(marker_strength or 0.0))
    normalized = min(2.5, strength / 0.004)
    radius = max(16, int(min(width, height) * (0.035 + (0.01 * normalized))))
    cross = max(26, int(radius * 1.4))
    line = max(4, int(min(width, height) * 0.008))

    draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=(255, 24, 24, 70))
    draw.ellipse((px - radius, py - radius, px + radius, py + radius), outline=(255, 36, 36, 255), width=line)
    draw.line((px - cross, py, px + cross, py), fill=(255, 36, 36, 255), width=max(3, line - 1))
    draw.line((px, py - cross, px, py + cross), fill=(255, 36, 36, 255), width=max(3, line - 1))

    label = (str(marker_label or "").strip() or "Bewegung")[:32]
    text_w = int(len(label) * max(10, int(min(width, height) * 0.02)))
    box_x = max(8, min(width - text_w - 26, px + radius + 10))
    box_y = max(8, py - radius - 40)
    box_h = 30
    draw.rectangle((box_x, box_y, box_x + text_w + 18, box_y + box_h), fill=(0, 0, 0, 170))
    draw.text((box_x + 9, box_y + 6), label, fill=(255, 90, 90, 255))

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()


def _steps_for_run(db: Session, module_key: str) -> list[dict]:
    rows = _module_postures(db, module_key, active_only=True)
    if rows:
        allowed_map = _load_allowed_module_map(db, [int(row.id) for row in rows])
        scoped_rows: list[GamePostureTemplate] = []
        for row in rows:
            allowed = allowed_map.get(int(row.id))
            if allowed is None:
                pool_key = _posture_pool_module_key(row.module_key)
                allowed = set(_default_allowed_module_keys_for_pool(pool_key))
            if module_key in allowed:
                scoped_rows.append(row)
        if not scoped_rows:
            return []
        rows = scoped_rows

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


def _default_movement_thresholds_for_module(module_key: str) -> dict:
    module_defaults = DEFAULT_MOVEMENT_THRESHOLDS_BY_MODULE.get(module_key)
    if module_defaults:
        return module_defaults
    return DEFAULT_MOVEMENT_THRESHOLDS_BY_MODULE["dont_move"]


def _default_start_countdown_seconds(module_key: str) -> int:
    if _is_single_pose_strict_module(module_key):
        return DEFAULT_STRICT_START_COUNTDOWN_SECONDS
    return 0


def _default_pose_similarity_thresholds_for_module(module_key: str) -> dict:
    if module_key == "posture_training":
        return {
            "easy": POSE_SIMILARITY_THRESHOLD_BY_DIFFICULTY["easy"],
            "medium": POSE_SIMILARITY_THRESHOLD_BY_DIFFICULTY["medium"],
            "hard": POSE_SIMILARITY_THRESHOLD_BY_DIFFICULTY["hard"],
        }
    if module_key == "dont_move":
        return {
            "easy": 45.0,
            "medium": 55.0,
            "hard": 65.0,
        }
    if module_key == "tiptoeing":
        return {
            # Tiptoeing uses these fields as green dominance deltas (%).
            "easy": 8.0,
            "medium": 10.0,
            "hard": 12.0,
        }
    return {
        "easy": 0.0,
        "medium": 0.0,
        "hard": 0.0,
    }


def _global_settings_payload(item: GameModuleSetting | None) -> dict:
    if item is None:
        return {
            "easy_target_multiplier": DEFAULT_EASY_TARGET_MULTIPLIER,
            "hard_target_multiplier": DEFAULT_HARD_TARGET_MULTIPLIER,
            "target_randomization_percent": DEFAULT_TARGET_RANDOMIZATION_PERCENT,
            "start_countdown_seconds": DEFAULT_STRICT_START_COUNTDOWN_SECONDS,
        }
    return {
        "easy_target_multiplier": float(item.easy_target_multiplier),
        "hard_target_multiplier": float(item.hard_target_multiplier),
        "target_randomization_percent": int(item.target_randomization_percent),
        "start_countdown_seconds": int(item.start_countdown_seconds or DEFAULT_STRICT_START_COUNTDOWN_SECONDS),
    }


def _module_settings_payload(item: GameModuleSetting | None, module_key: str) -> dict:
    defaults = _default_movement_thresholds_for_module(module_key)
    default_start_countdown = _default_start_countdown_seconds(module_key)
    default_pose_similarity = _default_pose_similarity_thresholds_for_module(module_key)
    if item is None:
        return {
            "easy_target_multiplier": DEFAULT_EASY_TARGET_MULTIPLIER,
            "hard_target_multiplier": DEFAULT_HARD_TARGET_MULTIPLIER,
            "target_randomization_percent": DEFAULT_TARGET_RANDOMIZATION_PERCENT,
            "start_countdown_seconds": default_start_countdown,
            "mask_image_url": None,
            "movement_easy_pose_deviation": float(defaults["easy"]["pose_deviation"]),
            "movement_easy_stillness": float(defaults["easy"]["stillness"]),
            "movement_medium_pose_deviation": float(defaults["medium"]["pose_deviation"]),
            "movement_medium_stillness": float(defaults["medium"]["stillness"]),
            "movement_hard_pose_deviation": float(defaults["hard"]["pose_deviation"]),
            "movement_hard_stillness": float(defaults["hard"]["stillness"]),
            "pose_similarity_min_score_easy": float(default_pose_similarity["easy"]),
            "pose_similarity_min_score_medium": float(default_pose_similarity["medium"]),
            "pose_similarity_min_score_hard": float(default_pose_similarity["hard"]),
            "movement_thresholds": {
                "easy": {
                    "pose_deviation": float(defaults["easy"]["pose_deviation"]),
                    "stillness": float(defaults["easy"]["stillness"]),
                },
                "medium": {
                    "pose_deviation": float(defaults["medium"]["pose_deviation"]),
                    "stillness": float(defaults["medium"]["stillness"]),
                },
                "hard": {
                    "pose_deviation": float(defaults["hard"]["pose_deviation"]),
                    "stillness": float(defaults["hard"]["stillness"]),
                },
            },
        }

    easy_pose = float(item.movement_easy_pose_deviation) if item.movement_easy_pose_deviation is not None else float(defaults["easy"]["pose_deviation"])
    easy_still = float(item.movement_easy_stillness) if item.movement_easy_stillness is not None else float(defaults["easy"]["stillness"])
    medium_pose = float(item.movement_medium_pose_deviation) if item.movement_medium_pose_deviation is not None else float(defaults["medium"]["pose_deviation"])
    medium_still = float(item.movement_medium_stillness) if item.movement_medium_stillness is not None else float(defaults["medium"]["stillness"])
    hard_pose = float(item.movement_hard_pose_deviation) if item.movement_hard_pose_deviation is not None else float(defaults["hard"]["pose_deviation"])
    hard_still = float(item.movement_hard_stillness) if item.movement_hard_stillness is not None else float(defaults["hard"]["stillness"])

    return {
        "easy_target_multiplier": item.easy_target_multiplier,
        "hard_target_multiplier": item.hard_target_multiplier,
        "target_randomization_percent": item.target_randomization_percent,
        "start_countdown_seconds": (
            int(item.start_countdown_seconds)
            if item.start_countdown_seconds is not None
            else default_start_countdown
        ),
        "mask_image_url": item.mask_image_url or None,
        "movement_easy_pose_deviation": easy_pose,
        "movement_easy_stillness": easy_still,
        "movement_medium_pose_deviation": medium_pose,
        "movement_medium_stillness": medium_still,
        "movement_hard_pose_deviation": hard_pose,
        "movement_hard_stillness": hard_still,
        "pose_similarity_min_score_easy": (
            float(item.pose_similarity_min_score_easy)
            if item.pose_similarity_min_score_easy is not None
            else float(default_pose_similarity["easy"])
        ),
        "pose_similarity_min_score_medium": (
            float(item.pose_similarity_min_score_medium)
            if item.pose_similarity_min_score_medium is not None
            else float(default_pose_similarity["medium"])
        ),
        "pose_similarity_min_score_hard": (
            float(item.pose_similarity_min_score_hard)
            if item.pose_similarity_min_score_hard is not None
            else float(default_pose_similarity["hard"])
        ),
        "movement_thresholds": {
            "easy": {
                "pose_deviation": easy_pose,
                "stillness": easy_still,
            },
            "medium": {
                "pose_deviation": medium_pose,
                "stillness": medium_still,
            },
            "hard": {
                "pose_deviation": hard_pose,
                "stillness": hard_still,
            },
        },
    }


def _verification_criteria_for_step(run: GameRun, step: GameRunStep) -> str:
    base_instruction = (step.instruction or "Keine Zusatzkriterien hinterlegt.").strip()

    if run.module_key == "tiptoeing":
        return (
            "Aufgabe: strenge Bildpruefung fuer Tiptoeing. "
            f"Soll-Pose: '{step.posture_name}'. "
            "Pflichtausschnitt: Fuesse, Knoechel und Bereich bis knapp unter die Knie muessen sichtbar sein. "
            "Virtueller Klotz-Regel: Die Person soll auf den Zehenspitzen stehen, als ob sie auf einem virtuellen Klotz steht. "
            "Verstoss: Sobald eine Ferse den virtuellen Klotzbereich beruehrt oder absinkt, ist das Ergebnis 'suspicious'. "
            f"Zusatzkriterien: {base_instruction} "
            "Bewerte 'confirmed' NUR wenn die Pose klar sichtbar ist und alle Regeln gleichzeitig eingehalten sind. "
            "Bei Unsicherheit, unvollstaendigem Ausschnitt, verdeckten Fersen oder unklarer Haltung immer 'suspicious'."
        )

    return (
        "Aufgabe: strenge Bildpruefung fuer eine konkrete Pose. "
        f"Soll-Pose: '{step.posture_name}'. "
        f"Soll-Kriterien: {base_instruction} "
        "Bewerte 'confirmed' NUR wenn die Pose klar sichtbar ist und mit Soll-Pose plus Kriterien uebereinstimmt. "
        "Wenn Koerperhaltung, Ausrichtung, Kamerawinkel oder Bildqualitaet keine sichere Zuordnung erlauben: 'suspicious'. "
        "Bei Teiltreffern oder Unsicherheit niemals 'confirmed'."
    )


def _load_module_settings(db: Session, module_key: str) -> GameModuleSetting | None:
    return db.query(GameModuleSetting).filter(GameModuleSetting.module_key == module_key).first()


def _load_global_settings(db: Session) -> GameModuleSetting | None:
    return _load_module_settings(db, GLOBAL_GAME_SETTINGS_KEY)


def _resolve_effective_settings(db: Session, payload: StartGameRunRequest) -> tuple[float, float, int]:
    configured_module = _load_module_settings(db, payload.module_key)
    module_payload = _module_settings_payload(configured_module, payload.module_key)
    configured_global = _load_global_settings(db)
    global_payload = _global_settings_payload(configured_global)
    easy = (
        payload.easy_target_multiplier
        if payload.easy_target_multiplier is not None
        else float(global_payload["easy_target_multiplier"] if configured_global is not None else module_payload["easy_target_multiplier"])
    )
    hard = (
        payload.hard_target_multiplier
        if payload.hard_target_multiplier is not None
        else float(global_payload["hard_target_multiplier"] if configured_global is not None else module_payload["hard_target_multiplier"])
    )
    randomization = (
        payload.target_randomization_percent
        if payload.target_randomization_percent is not None
        else int(global_payload["target_randomization_percent"] if configured_global is not None else module_payload["target_randomization_percent"])
    )
    return easy, hard, randomization


def _resolve_effective_start_countdown_seconds(db: Session, payload: StartGameRunRequest) -> int:
    if payload.start_countdown_seconds is not None:
        return max(0, min(60, int(payload.start_countdown_seconds)))
    configured_global = _load_global_settings(db)
    if configured_global is not None:
        global_payload = _global_settings_payload(configured_global)
        return max(0, min(60, int(global_payload.get("start_countdown_seconds", DEFAULT_STRICT_START_COUNTDOWN_SECONDS))))
    configured_module = _load_module_settings(db, payload.module_key)
    module_payload = _module_settings_payload(configured_module, payload.module_key)
    return max(0, min(60, int(module_payload.get("start_countdown_seconds", 0))))


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
    capture_rel_path: str | None,
    sample_only: bool,
    monitor_only: bool = False,
    pose_similarity: dict | None = None,
) -> None:
    meta = _load_run_summary_meta(run)
    checks = meta.get("checks")
    if not isinstance(checks, list):
        checks = []

    pose_score = None
    pose_threshold = None
    if isinstance(pose_similarity, dict):
        raw_score = pose_similarity.get("score")
        raw_threshold = pose_similarity.get("threshold")
        if isinstance(raw_score, (int, float)):
            pose_score = float(raw_score)
        if isinstance(raw_threshold, (int, float)):
            pose_threshold = float(raw_threshold)

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
            "monitor_only": bool(monitor_only),
            "pose_score": pose_score,
            "pose_threshold": pose_threshold,
            "capture_path": capture_rel_path,
            "capture_url": (f"/media/{capture_rel_path}" if capture_rel_path else None),
        }
    )

    meta["checks"] = checks
    run.summary_json = json.dumps(meta, ensure_ascii=True)


def _historical_pose_scores_for_step(run: GameRun, step_id: int) -> list[float]:
    meta = _load_run_summary_meta(run)
    checks = meta.get("checks")
    if not isinstance(checks, list):
        return []

    scores: list[float] = []
    for entry in checks:
        if not isinstance(entry, dict):
            continue
        if int(entry.get("step_id") or 0) != int(step_id):
            continue
        raw = entry.get("pose_score")
        if isinstance(raw, (int, float)):
            scores.append(float(raw))
    return scores


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

    try:
        _module = get_module(run.module_key)
        _module_title = _module.title if _module else run.module_key
        ai_assessment = generate_game_run_summary(report, _module_title)
        if ai_assessment:
            report["ai_assessment"] = ai_assessment
    except Exception:
        pass

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
def get_module_settings(module_key: str, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    item = _load_module_settings(db, module_key)
    return _module_settings_payload(item, module_key)


@router.get("/settings/global")
def get_global_game_settings(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    item = _load_global_settings(db)
    return _global_settings_payload(item)


@router.put("/settings/global")
def update_global_game_settings(
    payload: GlobalGameSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    item = _load_global_settings(db)
    if item is None:
        item = GameModuleSetting(module_key=GLOBAL_GAME_SETTINGS_KEY)
    item.easy_target_multiplier = payload.easy_target_multiplier
    item.hard_target_multiplier = payload.hard_target_multiplier
    item.target_randomization_percent = payload.target_randomization_percent
    item.start_countdown_seconds = payload.start_countdown_seconds
    db.add(item)
    db.commit()
    db.refresh(item)
    audit_log(
        "admin_game_global_settings_updated",
        actor_user_id=user.id,
        easy_target_multiplier=item.easy_target_multiplier,
        hard_target_multiplier=item.hard_target_multiplier,
        target_randomization_percent=item.target_randomization_percent,
        start_countdown_seconds=item.start_countdown_seconds,
    )
    return _global_settings_payload(item)


@router.put("/modules/{module_key}/settings")
def update_module_settings(
    module_key: str,
    payload: ModuleSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    item = _load_module_settings(db, module_key)
    if item is None:
        item = GameModuleSetting(module_key=module_key)
    item.easy_target_multiplier = payload.easy_target_multiplier
    item.hard_target_multiplier = payload.hard_target_multiplier
    item.target_randomization_percent = payload.target_randomization_percent
    item.start_countdown_seconds = payload.start_countdown_seconds
    item.movement_easy_pose_deviation = payload.movement_easy_pose_deviation
    item.movement_easy_stillness = payload.movement_easy_stillness
    item.movement_medium_pose_deviation = payload.movement_medium_pose_deviation
    item.movement_medium_stillness = payload.movement_medium_stillness
    item.movement_hard_pose_deviation = payload.movement_hard_pose_deviation
    item.movement_hard_stillness = payload.movement_hard_stillness
    item.pose_similarity_min_score_easy = payload.pose_similarity_min_score_easy
    item.pose_similarity_min_score_medium = payload.pose_similarity_min_score_medium
    item.pose_similarity_min_score_hard = payload.pose_similarity_min_score_hard
    db.add(item)
    db.commit()
    db.refresh(item)
    audit_log(
        "admin_game_module_settings_updated",
        actor_user_id=user.id,
        module_key=module_key,
        easy_target_multiplier=item.easy_target_multiplier,
        hard_target_multiplier=item.hard_target_multiplier,
        target_randomization_percent=item.target_randomization_percent,
        start_countdown_seconds=item.start_countdown_seconds,
        movement_easy_pose_deviation=item.movement_easy_pose_deviation,
        movement_easy_stillness=item.movement_easy_stillness,
        movement_medium_pose_deviation=item.movement_medium_pose_deviation,
        movement_medium_stillness=item.movement_medium_stillness,
        movement_hard_pose_deviation=item.movement_hard_pose_deviation,
        movement_hard_stillness=item.movement_hard_stillness,
        pose_similarity_min_score_easy=item.pose_similarity_min_score_easy,
        pose_similarity_min_score_medium=item.pose_similarity_min_score_medium,
        pose_similarity_min_score_hard=item.pose_similarity_min_score_hard,
    )
    return _module_settings_payload(item, module_key)


MAX_MASK_IMAGE_BYTES = 8 * 1024 * 1024


@router.post("/modules/{module_key}/mask")
async def upload_module_mask(
    module_key: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(raw) > MAX_MASK_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Mask image exceeds 8 MB limit")

    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        guessed_mime, _ = mimetypes.guess_type(file.filename or "mask.png")
        mime_type = guessed_mime or mime_type
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image format")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=415, detail="Uploaded image cannot be decoded")

    # Convert to RGBA PNG to preserve the green/black mask channels.
    out = io.BytesIO()
    img.convert("RGBA").save(out, format="PNG", optimize=True)
    processed = out.getvalue()

    rel_path = f"game_masks/{module_key}/{uuid4().hex}.png"
    target = _resolve_media_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(processed)

    ext = Path(file.filename or "mask.png").suffix.lower() or ".png"
    original_filename = f"mask_{module_key}{ext}"
    asset = MediaAsset(
        owner_user_id=None,
        media_kind="game_mask",
        storage_path=rel_path,
        original_filename=original_filename,
        mime_type="image/png",
        file_size_bytes=len(processed),
        visibility="shared",
    )
    db.add(asset)
    db.flush()

    mask_url = f"/api/media/{asset.id}/content"
    item = _load_module_settings(db, module_key)
    if item is None:
        item = GameModuleSetting(module_key=module_key)
    item.mask_image_url = mask_url
    db.add(item)
    db.commit()

    audit_log(
        "admin_game_module_mask_uploaded",
        actor_user_id=user.id,
        module_key=module_key,
        media_asset_id=asset.id,
        mask_url=mask_url,
    )
    return {"mask_image_url": mask_url}


@router.get("/modules/{module_key}/postures")
def list_module_postures(module_key: str, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    rows = _module_postures(db, module_key, active_only=False)
    allowed_map = _load_allowed_module_map(db, [int(row.id) for row in rows])
    items = []
    for row in rows:
        allowed = _resolved_allowed_module_keys(row, allowed_map)
        items.append(_template_payload(row, allowed_module_keys=allowed))
    return {"items": items}


@router.get("/modules/{module_key}/postures/available")
def list_available_module_postures(module_key: str, db: Session = Depends(get_db)) -> dict:
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    rows = _module_postures(db, module_key, active_only=True)
    allowed_map = _load_allowed_module_map(db, [int(row.id) for row in rows])
    items = []
    for row in rows:
        allowed = _resolved_allowed_module_keys(row, allowed_map)
        if module_key not in allowed:
            continue
        items.append(_template_payload(row, allowed_module_keys=allowed))
    return {"items": items}


def list_posture_matrix(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_session_user(request, db)
    modules = [as_public_module_payload(module) for module in list_modules()]
    rows = (
        db.query(GamePostureTemplate)
        .order_by(GamePostureTemplate.module_key.asc(), GamePostureTemplate.sort_order.asc(), GamePostureTemplate.id.asc())
        .all()
    )
    allowed_map = _load_allowed_module_map(db, [int(row.id) for row in rows])
    items = []
    for row in rows:
        allowed = _resolved_allowed_module_keys(row, allowed_map)
        items.append(_template_payload(row, allowed_module_keys=allowed))
    return {"modules": modules, "items": items}


def update_posture_matrix(payload: PostureMatrixBulkUpdateRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_admin_session_user(request, db)
    if not payload.items:
        return {"updated": 0, "requested": 0, "skipped": 0}

    posture_ids = sorted({int(item.posture_id) for item in payload.items})
    templates = (
        db.query(GamePostureTemplate)
        .filter(GamePostureTemplate.id.in_(posture_ids))
        .all()
    )
    template_by_id = {int(item.id): item for item in templates}

    updated = 0
    skipped = 0
    for item in payload.items:
        template = template_by_id.get(int(item.posture_id))
        if template is None:
            skipped += 1
            continue

        pool_key = _posture_pool_module_key(template.module_key)
        allowed = _normalize_allowed_module_keys(item.allowed_module_keys, pool_key, allow_empty=True)
        _set_allowed_module_keys(db, int(template.id), allowed)
        updated += 1

    db.commit()
    audit_log(
        "admin_game_posture_matrix_updated",
        actor_user_id=user.id,
        requested=len(payload.items),
        updated=updated,
        skipped=skipped,
    )
    return {"updated": updated, "requested": len(payload.items), "skipped": skipped}


@router.post("/modules/{module_key}/postures/upload-image")
async def upload_module_posture_image(
    module_key: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    raw = await file.read()
    processed, original_filename = _process_posture_image(raw, file.filename, file.content_type)
    asset = _store_posture_media(db, module_key, processed, original_filename)
    db.commit()
    db.refresh(asset)
    audit_log("admin_game_posture_image_uploaded", actor_user_id=user.id, module_key=module_key, media_id=asset.id)
    return _media_payload(asset)


@router.get("/modules/{module_key}/postures/export")
def export_module_postures_zip(module_key: str, request: Request, db: Session = Depends(get_db)):
    require_admin_session_user(request, db)
    module = get_module(module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")

    postures = _module_postures(db, module_key, active_only=False)
    allowed_map = _load_allowed_module_map(db, [int(row.id) for row in postures])
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
                "allowed_module_keys": _resolved_allowed_module_keys(posture, allowed_map),
            }
            if posture.reference_landmarks_json:
                item["reference_landmarks_json"] = posture.reference_landmarks_json

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
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
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
        existing_ids = [
            int(row[0])
            for row in (
                db.query(GamePostureTemplate.id)
                .filter(GamePostureTemplate.module_key == pool_key)
                .all()
            )
        ]
        if existing_ids:
            (
                db.query(GamePostureModuleAssignment)
                .filter(GamePostureModuleAssignment.posture_template_id.in_(existing_ids))
                .delete(synchronize_session=False)
            )
        (
            db.query(GamePostureTemplate)
            .filter(GamePostureTemplate.module_key == pool_key)
            .delete(synchronize_session=False)
        )

        imported = 0
        generated_reference_count = 0
        missing_reference_count = 0
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
            allowed_module_keys = _normalize_allowed_module_keys(
                item.get("allowed_module_keys"),
                pool_key,
                allow_empty=True,
            )
            imported_reference_json = item.get("reference_landmarks_json")
            parsed_reference_json = None
            if imported_reference_json is not None:
                if not isinstance(imported_reference_json, str):
                    raise HTTPException(
                        status_code=422,
                        detail=f"Posture entry #{idx} has invalid reference_landmarks_json",
                    )
                try:
                    parsed = json.loads(imported_reference_json)
                except json.JSONDecodeError as exc:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Posture entry #{idx} has invalid reference_landmarks_json",
                    ) from exc

                if not isinstance(parsed, dict):
                    raise HTTPException(
                        status_code=422,
                        detail=f"Posture entry #{idx} has invalid reference_landmarks_json",
                    )

                points = parsed.get("points")
                meta = parsed.get("meta")
                center = meta.get("center") if isinstance(meta, dict) else None
                scale = meta.get("scale") if isinstance(meta, dict) else None
                if not isinstance(points, dict) or not isinstance(meta, dict):
                    raise HTTPException(
                        status_code=422,
                        detail=f"Posture entry #{idx} has invalid reference_landmarks_json",
                    )
                if not isinstance(center, list) or len(center) != 2:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Posture entry #{idx} has invalid reference_landmarks_json",
                    )
                if not isinstance(scale, (int, float)) or float(scale) <= 0:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Posture entry #{idx} has invalid reference_landmarks_json",
                    )
                parsed_reference_json = json.dumps(parsed, ensure_ascii=True)

            template = GamePostureTemplate(
                module_key=pool_key,
                posture_key=posture_key[:120],
                title=title,
                image_url=resolved_image_url,
                instruction=instruction,
                target_seconds=target_seconds,
                sort_order=sort_order,
                is_active=is_active,
            )
            db.add(template)
            db.flush()
            reference_image_bytes = None
            if image_file:
                reference_image_bytes = processed
            else:
                reference_image_bytes = _try_load_posture_image_bytes_from_url(db, resolved_image_url)
            if parsed_reference_json:
                template.reference_landmarks_json = parsed_reference_json
                template.reference_landmarks_detected_at = datetime.now(timezone.utc)
            else:
                _refresh_reference_landmarks(template, reference_image_bytes)
                if template.reference_landmarks_json:
                    generated_reference_count += 1
                else:
                    missing_reference_count += 1
            _set_allowed_module_keys(db, int(template.id), allowed_module_keys)
            imported += 1

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except ValueError:
        db.rollback()
        raise HTTPException(status_code=422, detail="ZIP contains invalid numeric posture fields")
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Unexpected failure while importing posture ZIP",
            extra={
                "module_key": module_key,
                "upload_filename": file.filename,
                "upload_content_type": file.content_type,
                "zip_size_bytes": len(raw_zip),
                "items_count": len(items),
            },
            exc_info=exc,
        )
        print(
            f"[posture_import_error] module_key={module_key} file={file.filename} content_type={file.content_type}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        raise

    audit_log(
        "admin_game_postures_imported",
        actor_user_id=user.id,
        module_key=module_key,
        imported=imported,
        replaced=replaced,
        generated_reference_count=generated_reference_count,
        missing_reference_count=missing_reference_count,
    )
    return {
        "imported": imported,
        "replaced": replaced,
        "generated_reference_count": generated_reference_count,
        "missing_reference_count": missing_reference_count,
    }


@router.post("/modules/{module_key}/postures")
def create_module_posture(
    module_key: str,
    payload: PostureTemplateCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
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
    db.flush()
    _refresh_reference_landmarks(template, _try_load_posture_image_bytes_from_url(db, image_url))
    allowed_module_keys = _normalize_allowed_module_keys(payload.allowed_module_keys, pool_key, allow_empty=True)
    _set_allowed_module_keys(db, int(template.id), allowed_module_keys)
    db.commit()
    db.refresh(template)
    audit_log(
        "admin_game_posture_created",
        actor_user_id=user.id,
        module_key=module_key,
        posture_id=template.id,
        posture_key=template.posture_key,
    )
    return _template_payload(template, allowed_module_keys=allowed_module_keys)


@router.put("/modules/{module_key}/postures/{posture_id}")
def update_module_posture(
    module_key: str,
    posture_id: int,
    payload: PostureTemplateUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
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
        _refresh_reference_landmarks(template, _try_load_posture_image_bytes_from_url(db, next_image))
    if payload.instruction is not None:
        template.instruction = payload.instruction.strip() or None
    if payload.target_seconds is not None:
        template.target_seconds = payload.target_seconds
    if payload.sort_order is not None:
        template.sort_order = payload.sort_order
    if payload.is_active is not None:
        template.is_active = payload.is_active

    existing_allowed = _load_allowed_module_map(db, [int(template.id)]).get(int(template.id))
    if payload.allowed_module_keys is not None:
        next_allowed = _normalize_allowed_module_keys(payload.allowed_module_keys, pool_key, allow_empty=True)
        _set_allowed_module_keys(db, int(template.id), next_allowed)
    else:
        if existing_allowed is None:
            next_allowed = _default_allowed_module_keys_for_pool(pool_key)
        else:
            next_allowed = sorted(existing_allowed)

    if not template.image_url:
        raise HTTPException(status_code=422, detail="image_url is required")

    db.add(template)
    db.commit()
    db.refresh(template)
    audit_log(
        "admin_game_posture_updated",
        actor_user_id=user.id,
        module_key=module_key,
        posture_id=template.id,
        posture_key=template.posture_key,
    )
    return _template_payload(template, allowed_module_keys=next_allowed)


@router.delete("/modules/{module_key}/postures/{posture_id}")
def delete_module_posture(module_key: str, posture_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_admin_session_user(request, db)
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
    (
        db.query(GamePostureModuleAssignment)
        .filter(GamePostureModuleAssignment.posture_template_id == int(template.id))
        .delete(synchronize_session=False)
    )
    db.delete(template)
    db.commit()
    audit_log(
        "admin_game_posture_deleted",
        actor_user_id=user.id,
        module_key=module_key,
        posture_id=posture_id,
    )
    return {"deleted": posture_id}


@router.put("/modules/{module_key}/postures/{posture_id}/reference-pose")
def update_module_posture_reference_pose(
    module_key: str,
    posture_id: int,
    payload: PostureReferencePoseUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
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

    if payload.enabled:
        if payload.refresh or not template.reference_landmarks_json:
            image_bytes = _try_load_posture_image_bytes_from_url(db, template.image_url or "")
            if not image_bytes:
                raise HTTPException(status_code=422, detail="Posture image is unavailable for landmark extraction")
            _refresh_reference_landmarks(template, image_bytes)
            if not template.reference_landmarks_json:
                raise HTTPException(status_code=422, detail="No pose landmarks detected in posture image")
    else:
        template.reference_landmarks_json = None
        template.reference_landmarks_detected_at = None

    db.add(template)
    db.commit()
    db.refresh(template)

    allowed = _load_allowed_module_map(db, [int(template.id)]).get(int(template.id))
    if allowed is None:
        next_allowed = _default_allowed_module_keys_for_pool(pool_key)
    else:
        next_allowed = sorted(allowed)

    audit_log(
        "admin_game_posture_reference_pose_updated",
        actor_user_id=user.id,
        module_key=module_key,
        posture_id=posture_id,
        enabled=bool(template.reference_landmarks_json),
        refreshed=bool(payload.refresh and payload.enabled),
    )
    return _template_payload(template, allowed_module_keys=next_allowed)


@router.put("/modules/{module_key}/postures/{posture_id}/reference-pose/manual")
def update_module_posture_reference_pose_manual(
    module_key: str,
    posture_id: int,
    payload: PostureReferencePoseManualUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
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

    try:
        parsed = json.loads(payload.reference_landmarks_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="reference_landmarks_json is not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="reference_landmarks_json must be a JSON object")

    points = parsed.get("points")
    meta = parsed.get("meta")
    if not isinstance(points, dict) or not isinstance(meta, dict):
        raise HTTPException(status_code=422, detail="reference_landmarks_json must contain points and meta objects")

    center = meta.get("center")
    scale = meta.get("scale")
    if not isinstance(center, list) or len(center) != 2:
        raise HTTPException(status_code=422, detail="reference_landmarks_json.meta.center must have two values")
    if not isinstance(scale, (int, float)) or float(scale) <= 0:
        raise HTTPException(status_code=422, detail="reference_landmarks_json.meta.scale must be > 0")

    template.reference_landmarks_json = json.dumps(parsed, ensure_ascii=True)
    template.reference_landmarks_detected_at = datetime.now(timezone.utc)

    db.add(template)
    db.commit()
    db.refresh(template)

    allowed = _load_allowed_module_map(db, [int(template.id)]).get(int(template.id))
    if allowed is None:
        next_allowed = _default_allowed_module_keys_for_pool(pool_key)
    else:
        next_allowed = sorted(allowed)

    audit_log(
        "admin_game_posture_reference_pose_manual_updated",
        actor_user_id=user.id,
        module_key=module_key,
        posture_id=posture_id,
    )
    return _template_payload(template, allowed_module_keys=next_allowed)


@router.post("/modules/{module_key}/postures/{posture_id}/reference-pose/upload")
async def upload_module_posture_reference_pose_image(
    module_key: str,
    posture_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    user = require_admin_session_user(request, db)
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

    raw = await file.read()
    processed, _ = _process_posture_image(raw, file.filename, file.content_type)
    _refresh_reference_landmarks(template, processed)
    if not template.reference_landmarks_json:
        raise HTTPException(status_code=422, detail="No pose landmarks detected in uploaded reference image")

    db.add(template)
    db.commit()
    db.refresh(template)

    allowed = _load_allowed_module_map(db, [int(template.id)]).get(int(template.id))
    if allowed is None:
        next_allowed = _default_allowed_module_keys_for_pool(pool_key)
    else:
        next_allowed = sorted(allowed)

    audit_log(
        "admin_game_posture_reference_pose_uploaded",
        actor_user_id=user.id,
        module_key=module_key,
        posture_id=posture_id,
    )
    return _template_payload(template, allowed_module_keys=next_allowed)


@router.post("/sessions/{session_id}/runs/start")
def start_game_run(session_id: int, payload: StartGameRunRequest, db: Session = Depends(get_db)) -> dict:
    _load_session(db, session_id)
    module = get_module(payload.module_key)
    if not module:
        raise HTTPException(status_code=404, detail="Game module not found")
    difficulty = _difficulty_for(payload.module_key, payload.difficulty)
    if not difficulty:
        raise HTTPException(status_code=409, detail="Difficulty not supported for this module")

    effective_transition_seconds = int(payload.transition_seconds)
    effective_max_misses_before_penalty = int(payload.max_misses_before_penalty)
    if _is_single_pose_strict_module(module.key):
        effective_transition_seconds = _resolve_effective_start_countdown_seconds(db, payload)
        # Single-pose strict modules apply penalty per violation; threshold is neutralized.
        effective_max_misses_before_penalty = 1

    run = GameRun(
        session_id=session_id,
        module_key=module.key,
        difficulty_key=difficulty.key,
        initiated_by=payload.initiated_by,
        status="active",
        total_duration_seconds=payload.duration_minutes * 60,
        retry_extension_seconds=0,
        transition_seconds=effective_transition_seconds,
        max_misses_before_penalty=effective_max_misses_before_penalty,
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
    if _is_single_pose_strict_module(module.key):
        if module.key == "dont_move" and payload.selected_posture_key:
            selected_steps = [
                step
                for step in available_steps
                if (step.get("posture_key") or "") == payload.selected_posture_key
            ]
            if not selected_steps:
                raise HTTPException(status_code=422, detail="Selected posture is not available")
        else:
            selected_steps = [available_steps[0]]

        chosen = dict(selected_steps[0])
        chosen["target_seconds"] = max(5, int(payload.duration_minutes) * 60)
        selected_steps = [chosen]

    easy_multiplier, hard_multiplier, randomization_percent = _resolve_effective_settings(db, payload)
    target_multiplier = _difficulty_target_multiplier(payload.difficulty, easy_multiplier, hard_multiplier)

    if _is_single_pose_strict_module(module.key):
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
                (
                    f"Spiel gestartet: {module.title} | difficulty={difficulty.label} | "
                    f"duration_minutes={payload.duration_minutes} | "
                    f"session_penalty_per_violation_seconds={payload.session_penalty_seconds}"
                )
                if _is_single_pose_strict_module(module.key)
                else (
                    f"Spiel gestartet: {module.title} | difficulty={difficulty.label} | "
                    f"duration_minutes={payload.duration_minutes} | max_misses={effective_max_misses_before_penalty} | "
                    f"target_multiplier={target_multiplier} | target_randomization_percent={randomization_percent}"
                )
            ),
        )
    )

    db.commit()
    db.refresh(run)
    return _run_payload(db, run)


@router.get("/sessions/{session_id}/runs")
def list_session_game_runs(session_id: int, db: Session = Depends(get_db)) -> dict:
    runs = (
        db.query(GameRun)
        .filter(GameRun.session_id == session_id)
        .order_by(GameRun.started_at.desc())
        .all()
    )
    items = []
    for run in runs:
        summary: dict = {}
        if run.summary_json:
            try:
                summary = json.loads(run.summary_json)
            except json.JSONDecodeError:
                pass
        items.append(
            {
                "id": run.id,
                "module_key": run.module_key,
                "difficulty_key": run.difficulty_key,
                "status": run.status,
                "miss_count": run.miss_count,
                "total_duration_seconds": run.total_duration_seconds,
                "retry_extension_seconds": run.retry_extension_seconds,
                "session_penalty_applied": bool(run.session_penalty_applied),
                "started_at": _as_utc(run.started_at).isoformat() if run.started_at else None,
                "finished_at": _as_utc(run.finished_at).isoformat() if run.finished_at else None,
                "passed_steps": int(summary.get("passed_steps") or 0),
                "failed_steps": int(summary.get("failed_steps") or 0),
                "total_steps": int(summary.get("total_steps") or 0),
                "ai_assessment": summary.get("ai_assessment") or None,
            }
        )
    return {"items": items}


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
    monitor_only: bool = Form(default=False),
    marker_x: float | None = Form(default=None),
    marker_y: float | None = Form(default=None),
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

    if monitor_only and run.module_key != "posture_training":
        raise HTTPException(status_code=422, detail="monitor_only is only supported for posture_training")

    data = await file.read()
    capture_bytes = data
    if marker_x is not None or marker_y is not None:
        capture_bytes = _annotate_movement_capture(data, marker_x=marker_x, marker_y=marker_y)

    difficulty = _difficulty_for(run.module_key, run.difficulty_key)
    if difficulty is None:
        raise HTTPException(status_code=409, detail="Difficulty profile missing")

    pose_status, pose_analysis, pose_details = _evaluate_pose_similarity_for_step(
        db=db,
        run=run,
        step=step,
        image_bytes=data,
    )

    if monitor_only:
        status = "confirmed" if pose_status == "confirmed" else "suspicious"
        analysis = pose_analysis or ("Pose-Check bestaetigt." if status == "confirmed" else "Pose-Check nicht bestaetigt.")
    else:
        status, analysis = analyze_verification(
            image_bytes=data,
            filename=file.filename or "capture.jpg",
            requested_seal_number=None,
            observed_seal_number=observed_posture,
            verification_criteria=_verification_criteria_for_step(run, step),
            allow_heuristic_fallback=False,
        )
        if pose_status == "suspicious":
            status = "suspicious"
            analysis = f"{analysis} {pose_analysis}".strip()
        elif pose_status == "confirmed":
            analysis = f"{analysis} {pose_analysis}".strip()

        # For posture_training final checks, decide by average pose score over the full hold duration.
        if run.module_key == "posture_training" and not sample_only:
            threshold = None
            current_score = None
            if isinstance(pose_details, dict):
                raw_threshold = pose_details.get("threshold")
                raw_score = pose_details.get("score")
                if isinstance(raw_threshold, (int, float)):
                    threshold = float(raw_threshold)
                if isinstance(raw_score, (int, float)):
                    current_score = float(raw_score)

            scores = _historical_pose_scores_for_step(run, step.id)
            if current_score is not None:
                scores.append(current_score)

            if threshold is not None and scores:
                avg_score = sum(scores) / len(scores)
                status = "confirmed" if avg_score >= threshold else "suspicious"
                analysis = (
                    f"Durchschnittlicher Pose-Score {avg_score:.1f}/100 (min {threshold:.1f}; samples={len(scores)})."
                )

    capture_rel_path = None
    if not monitor_only:
        capture_rel_path = _store_game_verification_capture(
            run,
            capture_bytes,
            file.filename,
            run_number=int(step.verification_count or 0) + 1,
        )
    elif status != "confirmed":
        capture_rel_path = _store_game_verification_capture(
            run,
            capture_bytes,
            file.filename,
            run_number=int(step.verification_count or 0) + 1,
        )

    step.verification_count += 1
    step.last_analysis = analysis
    now = datetime.now(timezone.utc)

    def _handle_failed_step_with_retry_policy() -> None:
        nonlocal run, step

        run.miss_count += 1
        disable_retry_for_module = _is_single_pose_strict_module(run.module_key)

        if disable_retry_for_module:
            if run.session_penalty_seconds > 0:
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
                            "Session-Penalty pro Verfehlung ausgeloest: "
                            f"+{run.session_penalty_seconds}s (Verfehlung #{run.miss_count})."
                        ),
                    )
                )

            db.add(
                Message(
                    session_id=run.session_id,
                    role="system",
                    message_type="game_step_fail",
                    content=(
                        f"Bewegungsverstoss erkannt: {step.posture_name}. "
                        f"Verstoesse gesamt: {run.miss_count}."
                    ),
                )
            )
            return

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

    if monitor_only:
        # Monitor checks run frequently; avoid writing chat messages for every tick.
        pass
    elif sample_only:
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
            _handle_failed_step_with_retry_policy()
            if not _is_single_pose_strict_module(run.module_key):
                step.status = "failed"
                step.completed_at = now

            db.add(
                Message(
                    session_id=run.session_id,
                    role="system",
                    message_type="game_step_sample_fail",
                    content=(
                        f"Stichprobe fehlgeschlagen: {step.posture_name}"
                        if not _is_single_pose_strict_module(run.module_key)
                        else f"Bewegungsverstoss in Stichprobe erkannt: {step.posture_name}"
                    ),
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
        monitor_only=monitor_only,
        pose_similarity=pose_details,
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
            "pose_similarity_status": pose_status,
            "pose_similarity": pose_details,
            "capture_path": capture_rel_path,
            "capture_url": (f"/media/{capture_rel_path}" if capture_rel_path else None),
            "sample_only": sample_only,
            "monitor_only": monitor_only,
            "finalized": step.status != "pending",
        },
    }


@router.post("/runs/{run_id}/steps/{step_id}/movement-event")
async def register_movement_event(
    run_id: int,
    step_id: int,
    file: UploadFile = File(...),
    marker_x: float | None = Form(default=None),
    marker_y: float | None = Form(default=None),
    marker_label: str | None = Form(default=None),
    marker_strength: float | None = Form(default=None),
    reason: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    run = db.query(GameRun).filter(GameRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Game run not found")
    if run.status != "active":
        raise HTTPException(status_code=409, detail="Game run is not active")
    if not _is_single_pose_strict_module(run.module_key):
        raise HTTPException(status_code=409, detail="Movement events are only supported for strict single-pose modules")

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
    annotated = _annotate_movement_capture(
        data,
        marker_x=marker_x,
        marker_y=marker_y,
        marker_label=marker_label,
        marker_strength=marker_strength,
    )
    capture_rel_path = _store_game_verification_capture(
        run,
        annotated,
        file.filename,
        run_number=int(step.verification_count or 0) + 1,
    )
    now = datetime.now(timezone.utc)

    marker_note = ""
    if marker_x is not None and marker_y is not None:
        marker_note = f" | marker=({marker_x:.3f},{marker_y:.3f})"
    if marker_label:
        marker_note += f" | region={marker_label[:32]}"
    analysis = (reason or "Lokale Bewegungserkennung hat eine Abweichung erkannt.").strip() + marker_note

    step.verification_count += 1
    step.last_analysis = analysis
    run.miss_count += 1

    if run.session_penalty_seconds > 0:
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
                    "Session-Penalty pro Verfehlung ausgeloest: "
                    f"+{run.session_penalty_seconds}s (Verfehlung #{run.miss_count})."
                ),
            )
        )

    db.add(
        Message(
            session_id=run.session_id,
            role="system",
            message_type="game_step_fail",
            content=(
                f"Bewegungsverstoss erkannt: {step.posture_name}. "
                f"Verstoesse gesamt: {run.miss_count}."
            ),
        )
    )
    db.add(
        Message(
            session_id=run.session_id,
            role="system",
            message_type="game_step_sample_fail",
            content=f"Bewegungsverstoss in Echtzeit erkannt: {step.posture_name}",
        )
    )

    _append_run_check_entry(
        run,
        step=step,
        verification_status="suspicious",
        analysis=analysis,
        capture_rel_path=capture_rel_path,
        sample_only=True,
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
            "verification_status": "suspicious",
            "analysis": step.last_analysis,
            "capture_path": capture_rel_path,
            "capture_url": f"/media/{capture_rel_path}",
            "sample_only": True,
            "finalized": step.status != "pending",
        },
    }


@router.post("/runs/{run_id}/steps/{step_id}/complete")
def complete_strict_game_step(
    run_id: int,
    step_id: int,
    db: Session = Depends(get_db),
) -> dict:
    run = db.query(GameRun).filter(GameRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Game run not found")
    if run.status != "active":
        raise HTTPException(status_code=409, detail="Game run is not active")
    if not _is_single_pose_strict_module(run.module_key):
        raise HTTPException(status_code=409, detail="Complete endpoint is only supported for strict single-pose modules")

    step = (
        db.query(GameRunStep)
        .filter(GameRunStep.id == step_id, GameRunStep.run_id == run_id)
        .first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Game step not found")
    if step.status != "pending":
        raise HTTPException(status_code=409, detail="Game step is not pending")

    now = datetime.now(timezone.utc)
    step.status = "passed"
    step.completed_at = now
    step.last_analysis = "Haltephase ohne erkannte Bewegung abgeschlossen."

    db.add(
        Message(
            session_id=run.session_id,
            role="system",
            message_type="game_step_pass",
            content=f"Posture ohne Bewegungsverstoss abgeschlossen: {step.posture_name}",
        )
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
            "verification_status": "confirmed",
            "analysis": step.last_analysis,
            "capture_path": None,
            "capture_url": None,
            "sample_only": False,
            "finalized": step.status != "pending",
        },
    }
