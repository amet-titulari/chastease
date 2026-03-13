import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.media_asset import MediaAsset

router = APIRouter(prefix="/api/media", tags=["media"])

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024


class MediaUpdateRequest(BaseModel):
    visibility: str | None = Field(default=None, pattern="^(private|session|shared)$")


def _media_to_dict(asset: MediaAsset) -> dict:
    return {
        "id": asset.id,
        "media_kind": asset.media_kind,
        "original_filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "file_size_bytes": asset.file_size_bytes,
        "visibility": asset.visibility,
        "owner_user_id": asset.owner_user_id,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "content_url": f"/api/media/{asset.id}/content",
    }


def _resolve_storage_path(storage_path: str) -> Path:
    base_dir = Path(settings.media_dir).resolve()
    target = (base_dir / storage_path).resolve()
    if base_dir not in target.parents and target != base_dir:
        raise HTTPException(status_code=500, detail="Invalid media path")
    return target


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    owner_user_id: int | None = Form(default=None),
    visibility: str = Form(default="private"),
    db: Session = Depends(get_db),
) -> dict:
    if visibility not in {"private", "session", "shared"}:
        raise HTTPException(status_code=422, detail="visibility must be one of: private, session, shared")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(raw) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Avatar exceeds 5 MB limit")

    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_MIME_TYPES:
        guessed_mime, _ = mimetypes.guess_type(file.filename or "avatar.jpg")
        mime_type = guessed_mime or mime_type
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image format")

    extension = ALLOWED_MIME_TYPES[mime_type]
    rel_path = f"avatars/{uuid4().hex}{extension}"
    target = _resolve_storage_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)

    asset = MediaAsset(
        owner_user_id=owner_user_id,
        media_kind="avatar",
        storage_path=rel_path,
        original_filename=file.filename,
        mime_type=mime_type,
        file_size_bytes=len(raw),
        visibility=visibility,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _media_to_dict(asset)


@router.get("/{media_id}")
def get_media_metadata(media_id: int, db: Session = Depends(get_db)) -> dict:
    asset = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media not found")
    return _media_to_dict(asset)


@router.put("/{media_id}")
def update_media(media_id: int, payload: MediaUpdateRequest, db: Session = Depends(get_db)) -> dict:
    asset = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media not found")

    if payload.visibility is not None:
        asset.visibility = payload.visibility

    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _media_to_dict(asset)


@router.get("/{media_id}/content")
def get_media_content(media_id: int, db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media not found")

    target = _resolve_storage_path(asset.storage_path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Media file missing")

    return FileResponse(
        path=target,
        media_type=asset.mime_type,
        filename=asset.original_filename or target.name,
    )


@router.delete("/{media_id}")
def delete_media(media_id: int, db: Session = Depends(get_db)) -> dict:
    asset = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media not found")

    target = _resolve_storage_path(asset.storage_path)
    if target.exists() and target.is_file():
        target.unlink()

    db.delete(asset)
    db.commit()
    return {"deleted": media_id}
