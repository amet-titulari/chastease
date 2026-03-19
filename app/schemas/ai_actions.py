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


AIAction = Annotated[CreateTaskAction | UpdateTaskAction | FailTaskAction, Field(discriminator="type")]

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
        normalized.append(payload)

    return normalized