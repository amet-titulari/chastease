from dataclasses import dataclass


@dataclass
class TimerState:
    remaining_seconds: int
    frozen: bool = False


class TimerService:
    @staticmethod
    def add_time(state: TimerState, seconds: int) -> TimerState:
        return TimerState(remaining_seconds=state.remaining_seconds + max(0, seconds), frozen=state.frozen)

    @staticmethod
    def remove_time(state: TimerState, seconds: int) -> TimerState:
        remaining = max(0, state.remaining_seconds - max(0, seconds))
        return TimerState(remaining_seconds=remaining, frozen=state.frozen)

    @staticmethod
    def freeze(state: TimerState) -> TimerState:
        return TimerState(remaining_seconds=state.remaining_seconds, frozen=True)

    @staticmethod
    def unfreeze(state: TimerState) -> TimerState:
        return TimerState(remaining_seconds=state.remaining_seconds, frozen=False)
