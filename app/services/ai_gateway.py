from dataclasses import dataclass


@dataclass
class AIResponse:
    message: str
    actions: list[dict]
    mood: str
    intensity: int


class AIGateway:
    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str:
        max_duration_text = str(max_duration_seconds) if max_duration_seconds is not None else "kein Maximum"
        return (
            "KEUSCHHEITS-VERTRAG\n"
            f"Keyholder-Persona: {persona_name}\n"
            f"Wearer: {player_nickname}\n"
            f"Mindestdauer (Sek.): {min_duration_seconds}\n"
            f"Maximaldauer (Sek.): {max_duration_text}\n"
            "\n"
            "Dieser Entwurf wird mit der digitalen Signatur bindend.\n"
            "Sicherheitsmechanismen (Safeword/Ampel/Emergency) bleiben unveraenderlich."
        )
