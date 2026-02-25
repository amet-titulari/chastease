from pathlib import Path

from chastease.config import Config


def test_config_uses_secret_key_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "fixed-env-secret")
    cfg = Config()
    assert cfg.SECRET_KEY == "fixed-env-secret"


def test_config_persists_secret_key_file(monkeypatch, tmp_path: Path):
    key_file = tmp_path / "secret_key.txt"
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY_FILE", str(key_file))

    cfg_a = Config()
    cfg_b = Config()

    assert cfg_a.SECRET_KEY
    assert cfg_a.SECRET_KEY == cfg_b.SECRET_KEY
    assert key_file.exists()
    assert key_file.read_text(encoding="utf-8").strip() == cfg_a.SECRET_KEY
