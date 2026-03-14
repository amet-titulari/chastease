from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyProfile:
    key: str
    label: str
    retry_extension_seconds: int
    auto_capture_interval_seconds: int


@dataclass(frozen=True)
class GameStepDefinition:
    posture_key: str
    posture_name: str
    posture_image_url: str | None
    instruction: str
    target_seconds: int


@dataclass(frozen=True)
class GameModuleDefinition:
    key: str
    title: str
    summary: str
    supports_auto_capture: bool
    difficulties: tuple[DifficultyProfile, ...]
    base_steps: tuple[GameStepDefinition, ...]


def as_public_module_payload(module: GameModuleDefinition) -> dict:
    return {
        "key": module.key,
        "title": module.title,
        "summary": module.summary,
        "supports_auto_capture": module.supports_auto_capture,
        "difficulties": [
            {
                "key": diff.key,
                "label": diff.label,
                "retry_extension_seconds": diff.retry_extension_seconds,
                "auto_capture_interval_seconds": diff.auto_capture_interval_seconds,
            }
            for diff in module.difficulties
        ],
        "steps": [
            {
                "posture_key": step.posture_key,
                "posture_name": step.posture_name,
                "posture_image_url": step.posture_image_url,
                "instruction": step.instruction,
                "target_seconds": step.target_seconds,
            }
            for step in module.base_steps
        ],
    }
