from app.services.ai_gateway import AIGateway


def build_contract_text(
    persona_name: str,
    player_nickname: str,
    min_duration_seconds: int,
    max_duration_seconds: int | None,
) -> str:
    gateway = AIGateway()
    return gateway.generate_contract(
        persona_name=persona_name,
        player_nickname=player_nickname,
        min_duration_seconds=min_duration_seconds,
        max_duration_seconds=max_duration_seconds,
    )
