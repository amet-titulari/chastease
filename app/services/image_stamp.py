from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.config import settings


_FONT_PATH_CANDIDATES = {
    False: (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Tahoma.ttf",
        "/System/Library/Fonts/Supplemental/Verdana.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ),
    True: (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf",
        "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ),
}


def _timestamp_text(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _local_timestamp_text(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        tz = ZoneInfo(settings.local_timezone)
    except (ZoneInfoNotFoundError, Exception):
        tz = timezone.utc
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%d.%m.%Y %H:%M:%S %Z")


def _load_font(size: int, *, bold: bool = False):
    font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    desired_size = max(12, int(size))
    try:
        return ImageFont.truetype(font_name, size=desired_size)
    except Exception:
        for candidate in _FONT_PATH_CANDIDATES[bold]:
            try:
                if Path(candidate).exists():
                    return ImageFont.truetype(candidate, size=desired_size)
            except Exception:
                continue
        return ImageFont.load_default()


def _ellipsize_to_width(draw: ImageDraw.ImageDraw, text: str, max_width: int, font=None) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    bbox = draw.textbbox((0, 0), value, font=font)
    if int(bbox[2] - bbox[0]) <= max_width:
        return value

    ellipsis = "..."
    shortened = value
    while shortened:
        shortened = shortened[:-1].rstrip()
        candidate = f"{shortened}{ellipsis}"
        candidate_bbox = draw.textbbox((0, 0), candidate, font=font)
        if int(candidate_bbox[2] - candidate_bbox[0]) <= max_width:
            return candidate
    return ellipsis


def _fit_text_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    *,
    max_lines: int,
    font=None,
) -> list[str]:
    words = [part for part in str(text or "").replace("\n", " \n ").split(" ") if part != ""]
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        if word == "\n":
            if current.strip():
                lines.append(current.strip())
            current = ""
            continue
        proposal = word if not current else f"{current} {word}"
        proposal_bbox = draw.textbbox((0, 0), proposal, font=font)
        proposal_width = max(1, int(proposal_bbox[2] - proposal_bbox[0]))
        if proposal_width <= max_width or not current:
            current = proposal
            continue
        lines.append(current.strip())
        if len(lines) >= max_lines:
            lines[-1] = _ellipsize_to_width(draw, lines[-1], max_width, font=font)
            return lines
        current = word
    if current.strip():
        lines.append(current.strip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines:
        lines[-1] = _ellipsize_to_width(draw, lines[-1], max_width, font=font)
    return lines


def _draw_text_box(
    draw: ImageDraw.ImageDraw,
    *,
    anchor: str,
    image_width: int,
    image_height: int,
    title: str,
    body: str,
    font=None,
) -> None:
    label = str(title or "").strip()
    value = str(body or "").strip()
    if not label and not value:
        return

    scale_base = max(image_width, image_height)
    title_font = _load_font(max(38, int(scale_base * 0.028)), bold=True)
    body_font = _load_font(max(30, int(scale_base * 0.022)))
    pad_x = max(20, int(scale_base * 0.015))
    pad_y = max(16, int(scale_base * 0.012))
    line_gap = max(8, int(scale_base * 0.006))
    max_box_width = max(300, int(image_width * (0.48 if anchor.startswith("top") else 0.86)))
    min_box_width = max(220, int(image_width * (0.16 if anchor.startswith("top") else 0.44)))
    content_max_lines = 3 if anchor.startswith("top") else 4
    content_lines = _fit_text_lines(
        draw,
        value,
        max_box_width - (pad_x * 2),
        max_lines=content_max_lines,
        font=body_font,
    ) if value else []
    lines = ([label] if label else []) + content_lines
    if not lines:
        return

    line_heights: list[int] = []
    text_width = 0
    fonts = [title_font] + ([body_font] * max(0, len(lines) - 1))
    for index, line in enumerate(lines):
        font = fonts[min(index, len(fonts) - 1)]
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = max(text_width, int(bbox[2] - bbox[0]))
        line_heights.append(max(1, int(bbox[3] - bbox[1])))

    box_width = min(max_box_width, max(min_box_width, text_width + (pad_x * 2)))
    box_height = sum(line_heights) + (line_gap * max(0, len(lines) - 1)) + (pad_y * 2)

    margin_x = max(10, int(image_width * 0.012))
    margin_y = max(10, int(image_height * 0.014))
    if anchor == "top-left":
        x1 = margin_x
        y1 = margin_y
    elif anchor == "top-right":
        x1 = max(margin_x, image_width - margin_x - box_width)
        y1 = margin_y
    else:
        x1 = margin_x
        y1 = max(margin_y, image_height - margin_y - box_height)
        box_width = min(image_width - (margin_x * 2), box_width)

    x2 = min(image_width - margin_x, x1 + box_width)
    y2 = min(image_height - margin_y, y1 + box_height)
    radius = max(12, int(scale_base * 0.016))
    border_width = max(2, int(scale_base * 0.002))
    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=radius,
        fill=(5, 5, 5, 232),
        outline=(255, 255, 255, 72),
        width=border_width,
    )

    y = y1 + pad_y
    for index, line in enumerate(lines):
        font = fonts[min(index, len(fonts) - 1)]
        fill = (255, 221, 158, 255) if index == 0 and label else (255, 255, 255, 252)
        stroke_width = max(3, int(getattr(font, "size", 18) * 0.14))
        draw.text(
            (x1 + pad_x, y),
            line,
            fill=(0, 0, 0, 220),
            font=font,
            stroke_width=stroke_width,
            stroke_fill=(0, 0, 0, 220),
        )
        draw.text((x1 + pad_x, y), line, fill=fill, font=font)
        y += line_heights[index] + line_gap


def stamp_verification_proof(
    image_bytes: bytes,
    *,
    required_text: str | None = None,
    detected_text: str | None = None,
    now: datetime | None = None,
) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            image = ImageOps.exif_transpose(raw_img).convert("RGB")
    except Exception:
        return image_bytes

    width, height = image.size
    if width <= 0 or height <= 0:
        return image_bytes

    draw = ImageDraw.Draw(image, "RGBA")
    font = None
    _draw_text_box(
        draw,
        anchor="top-left",
        image_width=width,
        image_height=height,
        title="Gefordert",
        body=required_text or "-",
        font=font,
    )
    _draw_text_box(
        draw,
        anchor="top-right",
        image_width=width,
        image_height=height,
        title="Lokal",
        body=_local_timestamp_text(now),
        font=font,
    )
    _draw_text_box(
        draw,
        anchor="bottom",
        image_width=width,
        image_height=height,
        title="Erkannt",
        body=detected_text or "-",
        font=font,
    )

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue()


def stamp_game_verification_proof(
    image_bytes: bytes,
    *,
    required_text: str | None = None,
    detected_text: str | None = None,
    now: datetime | None = None,
) -> bytes:
    return stamp_verification_proof(
        image_bytes,
        required_text=required_text,
        detected_text=detected_text,
        now=now,
    )


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
    text = f"UTC {_timestamp_text(now)}"

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
    image.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue()
