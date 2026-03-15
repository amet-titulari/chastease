from app.services.games.base import DifficultyProfile, GameModuleDefinition, GameStepDefinition


TIPTOEING_MODULE = GameModuleDefinition(
    key="tiptoeing",
    title="Tiptoeing",
    summary="Single-Pose-Stillhalte-Modul auf Zehenspitzen mit strenger AI-Verifikation.",
    supports_auto_capture=True,
    difficulties=(
        DifficultyProfile(
            key="easy",
            label="Leicht",
            retry_extension_seconds=30,
            auto_capture_interval_seconds=14,
        ),
        DifficultyProfile(
            key="medium",
            label="Mittel",
            retry_extension_seconds=75,
            auto_capture_interval_seconds=10,
        ),
        DifficultyProfile(
            key="hard",
            label="Schwer",
            retry_extension_seconds=120,
            auto_capture_interval_seconds=8,
        ),
    ),
    base_steps=(
        GameStepDefinition(
            posture_key="tiptoeing_hold",
            posture_name="Auf Zehenspitzen stehen",
            posture_image_url="/static/img/postures/stand.jpg",
            instruction="Gehe auf die Zehenspitzen, halte den Oberkoerper ruhig und vermeide Korrekturbewegungen.",
            target_seconds=150,
        ),
    ),
)