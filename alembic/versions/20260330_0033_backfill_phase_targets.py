"""backfill_phase_targets

Revision ID: 0033
Revises: 0032
Create Date: 2026-03-30 18:20:00
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


_AMETARA_PHASE_META = {
    "phase_1": {
        "phase_weight": 1.0,
        "min_phase_duration_hours": 48,
        "score_targets": {"trust": 4, "obedience": 5, "resistance": 2, "favor": 3, "strictness": 3, "frustration": 2, "attachment": 4},
    },
    "phase_2": {
        "phase_weight": 1.2,
        "min_phase_duration_hours": 72,
        "score_targets": {"trust": 5, "obedience": 7, "resistance": 3, "favor": 4, "strictness": 4, "frustration": 4, "attachment": 5},
    },
    "phase_3": {
        "phase_weight": 1.45,
        "min_phase_duration_hours": 96,
        "score_targets": {"trust": 6, "obedience": 8, "resistance": 5, "favor": 5, "strictness": 5, "frustration": 6, "attachment": 5},
    },
    "phase_4": {
        "phase_weight": 1.75,
        "min_phase_duration_hours": 144,
        "score_targets": {"trust": 7, "obedience": 9, "resistance": 6, "favor": 6, "strictness": 6, "frustration": 7, "attachment": 6},
    },
    "phase_5": {
        "phase_weight": 1.55,
        "min_phase_duration_hours": 168,
        "score_targets": {"trust": 8, "obedience": 10, "resistance": 7, "favor": 7, "strictness": 7, "frustration": 8, "attachment": 7},
    },
    "phase_6": {
        "phase_weight": 0.95,
        "min_phase_duration_hours": 72,
        "score_targets": {"trust": 5, "obedience": 6, "resistance": 4, "favor": 4, "strictness": 4, "frustration": 5, "attachment": 6},
    },
}


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, phases_json FROM scenarios WHERE key = :key"),
        {"key": "ametara_titulari_devotion_protocol"},
    ).fetchall()
    for row in rows:
        try:
            phases = json.loads(row.phases_json or "[]")
        except Exception:
            continue
        if not isinstance(phases, list):
            continue
        changed = False
        for item in phases:
            if not isinstance(item, dict):
                continue
            phase_id = str(item.get("phase_id") or "").strip()
            meta = _AMETARA_PHASE_META.get(phase_id)
            if not meta:
                continue
            for key, value in meta.items():
                if item.get(key) != value:
                    item[key] = value
                    changed = True
        if changed:
            bind.execute(
                sa.text("UPDATE scenarios SET phases_json = :phases_json WHERE id = :id"),
                {"id": row.id, "phases_json": json.dumps(phases, ensure_ascii=False)},
            )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, phases_json FROM scenarios WHERE key = :key"),
        {"key": "ametara_titulari_devotion_protocol"},
    ).fetchall()
    for row in rows:
        try:
            phases = json.loads(row.phases_json or "[]")
        except Exception:
            continue
        if not isinstance(phases, list):
            continue
        changed = False
        for item in phases:
            if not isinstance(item, dict):
                continue
            if any(key in item for key in ("score_targets", "phase_weight", "min_phase_duration_hours")):
                item.pop("score_targets", None)
                item.pop("phase_weight", None)
                item.pop("min_phase_duration_hours", None)
                changed = True
        if changed:
            bind.execute(
                sa.text("UPDATE scenarios SET phases_json = :phases_json WHERE id = :id"),
                {"id": row.id, "phases_json": json.dumps(phases, ensure_ascii=False)},
            )
