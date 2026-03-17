from app.services.games.base import DifficultyProfile, GameModuleDefinition, GameStepDefinition


POSTURE_TRAINING_MODULE = GameModuleDefinition(
    key="posture_training",
    title="Posture Training",
    summary="Gefuehrtes Haltungsprogramm mit automatischer Kamera-Verifikation.",
    supports_auto_capture=True,
    difficulties=(
        DifficultyProfile(
            key="easy",
            label="Leicht",
            retry_extension_seconds=45,
            auto_capture_interval_seconds=15,
        ),
        DifficultyProfile(
            key="medium",
            label="Mittel",
            retry_extension_seconds=90,
            auto_capture_interval_seconds=12,
        ),
        DifficultyProfile(
            key="hard",
            label="Schwer",
            retry_extension_seconds=150,
            auto_capture_interval_seconds=10,
        ),
    ),
    base_steps=(
        GameStepDefinition(
            posture_key="posture_stand",
            posture_name="Stiller Stand",
            posture_image_url="/static/img/postures/stand.jpg",
            instruction="Aufrecht stehen, Schultern tief, Kinn neutral, ruhig atmen.",
            target_seconds=150,
        ),
        GameStepDefinition(
            posture_key="posture_kneel",
            posture_name="Knieposition",
            posture_image_url="/static/img/postures/kneel.jpg",
            instruction="Knieposition stabil halten, Blick gesenkt, Atmung kontrollieren.",
            target_seconds=60,
        ),
        GameStepDefinition(
            posture_key="posture_hands_back",
            posture_name="Haende hinter Ruecken",
            posture_image_url="/static/img/postures/hands_back.jpg",
            instruction="Stehend, Haende hinter dem Ruecken, Brust offen, ruhig bleiben.",
            target_seconds=120,
        ),
    ),
)
