from dataclasses import dataclass


@dataclass
class ToolPolicy:
    allow_execute: bool = True
    allow_suggest: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolPolicy] = {}

    def register(self, tool_name: str, policy: ToolPolicy) -> None:
        self._tools[tool_name.strip().lower()] = policy

    def is_registered(self, tool_name: str) -> bool:
        return tool_name.strip().lower() in self._tools

    def is_allowed(self, tool_name: str, mode: str = "execute") -> bool:
        policy = self._tools.get(tool_name.strip().lower())
        if policy is None:
            return False
        if mode == "suggest":
            return policy.allow_suggest
        return policy.allow_execute

    def list_tools(self, mode: str = "execute") -> list[str]:
        names: list[str] = []
        for name in sorted(self._tools.keys()):
            if self.is_allowed(name, mode=mode):
                names.append(name)
        return names


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("pause_timer", ToolPolicy(allow_execute=True, allow_suggest=True))
    registry.register("unpause_timer", ToolPolicy(allow_execute=True, allow_suggest=True))
    registry.register("add_time", ToolPolicy(allow_execute=True, allow_suggest=True))
    registry.register("reduce_time", ToolPolicy(allow_execute=True, allow_suggest=True))
    registry.register("update_session_settings", ToolPolicy(allow_execute=True, allow_suggest=True))
    registry.register("ttlock_open", ToolPolicy(allow_execute=True, allow_suggest=True))
    registry.register("ttlock_close", ToolPolicy(allow_execute=True, allow_suggest=True))
    registry.register("chaster_open", ToolPolicy(allow_execute=False, allow_suggest=True))
    registry.register("emlalock_open", ToolPolicy(allow_execute=False, allow_suggest=True))
    return registry
