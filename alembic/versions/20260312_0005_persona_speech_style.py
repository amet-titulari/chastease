"""replace communication_style with speech_style_tone and speech_style_dominance on personas

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("personas", sa.Column("speech_style_tone", sa.String(60), nullable=True))
    op.add_column("personas", sa.Column("speech_style_dominance", sa.String(60), nullable=True))

    # Best-effort migration: split existing "warm, gentle-dominant" → tone / dominance
    op.execute(
        """
        UPDATE personas
        SET
            speech_style_tone = CASE
                WHEN communication_style LIKE '%,%'
                THEN TRIM(SUBSTR(communication_style, 1, INSTR(communication_style, ',') - 1))
                ELSE TRIM(communication_style)
            END,
            speech_style_dominance = CASE
                WHEN communication_style LIKE '%,%'
                THEN TRIM(SUBSTR(communication_style, INSTR(communication_style, ',') + 1))
                ELSE NULL
            END
        WHERE communication_style IS NOT NULL
        """
    )

    op.drop_column("personas", "communication_style")


def downgrade() -> None:
    op.add_column("personas", sa.Column("communication_style", sa.String(120), nullable=True))

    op.execute(
        """
        UPDATE personas
        SET communication_style = CASE
            WHEN speech_style_tone IS NOT NULL AND speech_style_dominance IS NOT NULL
            THEN speech_style_tone || ', ' || speech_style_dominance
            WHEN speech_style_tone IS NOT NULL
            THEN speech_style_tone
            WHEN speech_style_dominance IS NOT NULL
            THEN speech_style_dominance
            ELSE NULL
        END
        WHERE speech_style_tone IS NOT NULL OR speech_style_dominance IS NOT NULL
        """
    )

    op.drop_column("personas", "speech_style_dominance")
    op.drop_column("personas", "speech_style_tone")
