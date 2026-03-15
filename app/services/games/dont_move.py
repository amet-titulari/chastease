from app.services.games.base import DifficultyProfile, GameModuleDefinition, GameStepDefinition


DONT_MOVE_MODULE = GameModuleDefinition(
    key="dont_move",
    title="Don't move",
    summary="Stillehalte-Modul mit klaren Positionen, langer Haltezeit und AI-Verifikation.",
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
            posture_key="dont_move_stand_neutral",
            posture_name="Neutral stehen",
            posture_image_url="/static/img/postures/stand.jpg",
            instruction="Stehe aufrecht und ruhig. Vermeide sichtbare Gewichtsverlagerung.",
            target_seconds=150,
        ),
        GameStepDefinition(
            posture_key="dont_move_hands_back",
            posture_name="Haende hinter dem Ruecken",
            posture_image_url="/static/img/postures/hands_back.jpg",
            instruction="Bleibe still, Haende hinter dem Ruecken, Blick stabil nach vorne.",
            target_seconds=180,
        ),
        GameStepDefinition(
            posture_key="dont_move_kneel_hold",
            posture_name="Knieposition halten",
            posture_image_url="/static/img/postures/kneel.jpg",
            instruction="Gehe in die Knieposition und halte die Haltung ohne Korrekturbewegungen.",
            target_seconds=140,
        ),
    ),
)