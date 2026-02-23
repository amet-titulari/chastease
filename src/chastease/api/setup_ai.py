from fastapi import Request

from chastease.api import routes as legacy


def extract_pending_actions(narration: str) -> tuple[str, list[dict], list[dict]]:
    return legacy._extract_pending_actions(narration)


def generate_ai_narration_for_setup_preview(
    db,
    request: Request,
    user_id: str,
    action: str,
    language: str,
    psychogram: dict,
    policy: dict,
    attachments: list[dict] | None = None,
) -> str:
    return legacy._generate_ai_narration_for_setup_preview(
        db,
        request,
        user_id,
        action,
        language,
        psychogram,
        policy,
        attachments,
    )


def generate_psychogram_analysis_with_end_date_for_setup(
    db,
    request: Request,
    setup_session: dict,
) -> tuple[str, str | None]:
    return legacy._generate_psychogram_analysis_with_end_date_for_setup(db, request, setup_session)


def generate_contract_for_setup(db, request: Request, setup_session: dict) -> str:
    return legacy._generate_contract_for_setup(db, request, setup_session)
