from app.services.games.base import GameModuleDefinition
from app.services.games.posture_training import POSTURE_TRAINING_MODULE


GAME_MODULES: tuple[GameModuleDefinition, ...] = (
    POSTURE_TRAINING_MODULE,
)


def list_modules() -> tuple[GameModuleDefinition, ...]:
    return GAME_MODULES


def get_module(module_key: str) -> GameModuleDefinition | None:
    for module in GAME_MODULES:
        if module.key == module_key:
            return module
    return None
