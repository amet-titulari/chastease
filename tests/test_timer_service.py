from app.services.timer_service import TimerService, TimerState


def test_add_and_remove_time():
    state = TimerState(remaining_seconds=120)
    state = TimerService.add_time(state, 30)
    assert state.remaining_seconds == 150

    state = TimerService.remove_time(state, 60)
    assert state.remaining_seconds == 90


def test_freeze_unfreeze():
    state = TimerState(remaining_seconds=180)
    frozen = TimerService.freeze(state)
    assert frozen.frozen is True

    unfrozen = TimerService.unfreeze(frozen)
    assert unfrozen.frozen is False
