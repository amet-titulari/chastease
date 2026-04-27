from app.services.toy_profile import get_toy_profile_from_preferences, merge_toy_profile


def test_merge_toy_profile_preserves_existing_non_managed_fields():
    merged = merge_toy_profile(
        {
            "lovense_policy": {"allow_presets": False},
            "provider": "none",
            "default_intensity": 4,
        },
        {
            "provider": "lovense",
            "enabled": True,
            "preferred_preset": "wave_ladder",
            "default_intensity": 14,
        },
    )

    assert merged["lovense_policy"] == {"allow_presets": False}
    assert merged["provider"] == "lovense"
    assert merged["enabled"] is True
    assert merged["preferred_preset"] == "wave_ladder"
    assert merged["default_intensity"] == 14


def test_get_toy_profile_from_preferences_returns_clamped_defaults():
    profile = get_toy_profile_from_preferences(
        {
            "toys": {
                "provider": "unknown",
                "enabled": "true",
                "preferred_preset": "invalid",
                "default_intensity": 99,
                "default_duration_seconds": -5,
                "default_pause_seconds": 400,
                "default_loops": 0,
            }
        }
    )

    assert profile["provider"] == "none"
    assert profile["enabled"] is True
    assert profile["preferred_preset"] == ""
    assert profile["default_intensity"] == 20
    assert profile["default_duration_seconds"] == 1
    assert profile["default_pause_seconds"] == 300
    assert profile["default_loops"] == 1


def test_get_toy_profile_accepts_coyote_aliases():
    profile = get_toy_profile_from_preferences({"toys": {"provider": "howl", "enabled": True}})
    assert profile["provider"] == "coyote"
    assert profile["enabled"] is True
