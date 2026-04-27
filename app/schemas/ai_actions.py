from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator


class _BaseActionModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


def _parse_positive_int(value: Any) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("must be positive")
    return parsed


def _parse_optional_positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return _parse_positive_int(value)


class CreateTaskAction(_BaseActionModel):
    type: Literal["create_task"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    deadline_minutes: int | None = None
    requires_verification: bool | None = None
    verification_criteria: str | None = Field(default=None, max_length=2000)
    consequence_type: str | None = Field(default=None, max_length=80)
    consequence_value: Any | None = None

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("deadline_minutes", mode="before")
    @classmethod
    def _validate_deadline_minutes(cls, value: Any) -> int | None:
        return _parse_optional_positive_int(value)

    @field_validator("verification_criteria", "consequence_type", mode="before")
    @classmethod
    def _empty_strings_to_none(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value).strip() or None


class UpdateTaskAction(_BaseActionModel):
    type: Literal["update_task"]
    task_id: int
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    deadline_minutes: int | None = None

    @field_validator("task_id", mode="before")
    @classmethod
    def _validate_task_id(cls, value: Any) -> int:
        return _parse_positive_int(value)

    @field_validator("title", mode="before")
    @classmethod
    def _validate_title(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("title must not be empty when provided")
        return text

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("deadline_minutes", mode="before")
    @classmethod
    def _validate_deadline_minutes(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        return _parse_positive_int(value)


class FailTaskAction(_BaseActionModel):
    type: Literal["fail_task"]
    task_id: int

    @field_validator("task_id", mode="before")
    @classmethod
    def _validate_task_id(cls, value: Any) -> int:
        return _parse_positive_int(value)


class UpdateRoleplayStateAction(_BaseActionModel):
    type: Literal["update_roleplay_state"]
    relationship: dict[str, Any] | None = None
    protocol: dict[str, Any] | None = None
    scene: dict[str, Any] | None = None

    @field_validator("relationship", "protocol", "scene", mode="before")
    @classmethod
    def _validate_optional_dict(cls, value: Any) -> dict[str, Any] | None:
        if value in (None, ""):
            return None
        if not isinstance(value, dict):
            raise ValueError("must be an object when provided")
        return value


class LovenseControlAction(_BaseActionModel):
    type: Literal["lovense_control"]
    command: Literal["vibrate", "pulse", "wave", "stop", "preset"]
    intensity: int | None = None
    duration_seconds: int | None = None
    pause_seconds: int | None = None
    loops: int | None = None
    preset: str | None = Field(default=None, max_length=80)

    @field_validator("intensity", mode="before")
    @classmethod
    def _validate_intensity(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 20:
            raise ValueError("intensity must be between 1 and 20")
        return parsed

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def _validate_duration_seconds(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 120:
            raise ValueError("duration_seconds must be between 1 and 120")
        return parsed

    @field_validator("pause_seconds", mode="before")
    @classmethod
    def _validate_pause_seconds(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 0 or parsed > 60:
            raise ValueError("pause_seconds must be between 0 and 60")
        return parsed

    @field_validator("loops", mode="before")
    @classmethod
    def _validate_loops(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 10:
            raise ValueError("loops must be between 1 and 10")
        return parsed


class LovenseSessionStep(_BaseActionModel):
    command: Literal["vibrate", "pulse", "wave", "stop", "preset", "pause"]
    intensity: int | None = None
    duration_seconds: int | None = None
    preset: str | None = Field(default=None, max_length=80)

    @field_validator("intensity", mode="before")
    @classmethod
    def _validate_intensity(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 20:
            raise ValueError("intensity must be between 1 and 20")
        return parsed

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def _validate_duration_seconds(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 180:
            raise ValueError("duration_seconds must be between 1 and 180")
        return parsed


class LovenseSessionPlanAction(_BaseActionModel):
    type: Literal["lovense_session_plan"]
    title: str | None = Field(default=None, max_length=120)
    mode: Literal["replace", "append"] = "replace"
    steps: list[LovenseSessionStep] = Field(min_length=1, max_length=24)

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        return text[:120] if text else None

    @field_validator("steps")
    @classmethod
    def _validate_steps(cls, value: list[LovenseSessionStep]) -> list[LovenseSessionStep]:
        total_seconds = 0
        for step in value:
            command = step.command
            if command == "pause":
                if step.duration_seconds is None:
                    raise ValueError("pause steps require duration_seconds")
            elif command == "stop":
                pass
            elif command == "preset":
                if step.duration_seconds is None:
                    raise ValueError("preset steps require duration_seconds")
                if step.preset is None:
                    raise ValueError("preset steps require preset")
            else:
                if step.duration_seconds is None:
                    raise ValueError(f"{command} steps require duration_seconds")
                if step.intensity is None:
                    raise ValueError(f"{command} steps require intensity")
            total_seconds += int(step.duration_seconds or 0)
        if total_seconds > 900:
            raise ValueError("lovense session plans must stay within 900 seconds total")
        return value


class ToyControlAction(_BaseActionModel):
    type: Literal["toy_control"]
    command: Literal["vibrate", "pulse", "wave", "stop", "preset"]
    intensity: int | None = None
    duration_seconds: int | None = None
    pause_seconds: int | None = None
    loops: int | None = None
    preset: str | None = Field(default=None, max_length=80)

    @field_validator("intensity", mode="before")
    @classmethod
    def _validate_intensity(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 20:
            raise ValueError("intensity must be between 1 and 20")
        return parsed

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def _validate_duration_seconds(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 120:
            raise ValueError("duration_seconds must be between 1 and 120")
        return parsed

    @field_validator("pause_seconds", mode="before")
    @classmethod
    def _validate_pause_seconds(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 0 or parsed > 60:
            raise ValueError("pause_seconds must be between 0 and 60")
        return parsed

    @field_validator("loops", mode="before")
    @classmethod
    def _validate_loops(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        if parsed < 1 or parsed > 10:
            raise ValueError("loops must be between 1 and 10")
        return parsed


class ToySessionPlanAction(_BaseActionModel):
    type: Literal["toy_session_plan"]
    title: str | None = Field(default=None, max_length=120)
    mode: Literal["replace", "append"] = "replace"
    steps: list[LovenseSessionStep] = Field(min_length=1, max_length=24)

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: Any) -> str | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        return text[:120] if text else None

    @field_validator("steps")
    @classmethod
    def _validate_steps(cls, value: list[LovenseSessionStep]) -> list[LovenseSessionStep]:
        total_seconds = 0
        for step in value:
            command = step.command
            if command == "pause":
                if step.duration_seconds is None:
                    raise ValueError("pause steps require duration_seconds")
            elif command == "stop":
                pass
            elif command == "preset":
                if step.duration_seconds is None:
                    raise ValueError("preset steps require duration_seconds")
                if step.preset is None:
                    raise ValueError("preset steps require preset")
            else:
                if step.duration_seconds is None:
                    raise ValueError(f"{command} steps require duration_seconds")
                if step.intensity is None:
                    raise ValueError(f"{command} steps require intensity")
            total_seconds += int(step.duration_seconds or 0)
        if total_seconds > 900:
            raise ValueError("toy session plans must stay within 900 seconds total")
        return value


AIAction = Annotated[
    CreateTaskAction
    | UpdateTaskAction
    | FailTaskAction
    | UpdateRoleplayStateAction
    | LovenseControlAction
    | LovenseSessionPlanAction
    | ToyControlAction
    | ToySessionPlanAction,
    Field(discriminator="type"),
]

_ACTION_ADAPTER = TypeAdapter(AIAction)


def normalize_action_payloads(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for raw_action in value:
        if not isinstance(raw_action, dict):
            continue
        try:
            action = _ACTION_ADAPTER.validate_python(raw_action)
        except ValidationError:
            continue

        payload = action.model_dump(exclude_none=True)
        if payload.get("type") == "update_task":
            if not any(key in payload for key in ("title", "description", "deadline_minutes")):
                continue
        if payload.get("type") == "update_roleplay_state":
            if not any(key in payload for key in ("relationship", "protocol", "scene")):
                continue
        if payload.get("type") == "lovense_control":
            command = payload.get("command")
            if command == "preset" and not payload.get("preset"):
                continue
        if payload.get("type") == "toy_control":
            command = payload.get("command")
            if command == "preset" and not payload.get("preset"):
                continue
        if payload.get("type") == "lovense_session_plan":
            if not payload.get("steps"):
                continue
            payload.setdefault("mode", "replace")
        if payload.get("type") == "toy_session_plan":
            if not payload.get("steps"):
                continue
            payload.setdefault("mode", "replace")
        normalized.append(payload)

    return normalized
