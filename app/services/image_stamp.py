from __future__ import annotations

import io
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageOps


def _timestamp_text(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stamp_verification_timestamp(image_bytes: bytes, now: datetime | None = None) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            image = ImageOps.exif_transpose(raw_img).convert("RGB")
    except Exception:
        return image_bytes

    width, height = image.size
    if width <= 0 or height <= 0:
        return image_bytes

    draw = ImageDraw.Draw(image, "RGBA")
    text = f"UTC { _timestamp_text(now) }"

    font = None
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = max(1, int(text_bbox[2] - text_bbox[0]))
    text_h = max(1, int(text_bbox[3] - text_bbox[1]))

    pad_x = max(8, int(width * 0.01))
    pad_y = max(6, int(height * 0.008))
    box_x2 = width - max(10, int(width * 0.012))
    box_x1 = max(10, box_x2 - text_w - (pad_x * 2))
    box_y1 = max(10, int(height * 0.014))
    box_y2 = box_y1 + text_h + (pad_y * 2)

    draw.rectangle((box_x1, box_y1, box_x2, box_y2), fill=(0, 0, 0, 170))
    draw.text((box_x1 + pad_x, box_y1 + pad_y), text, fill=(255, 255, 255, 240), font=font)

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()
