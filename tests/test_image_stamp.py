from unittest.mock import patch

from PIL import ImageFont

from app.services import image_stamp


def test_load_font_uses_system_path_when_named_font_fails(monkeypatch):
    calls: list[str] = []
    fallback_font = ImageFont.load_default()

    def fake_exists(self):
        return str(self) == "/tmp/TestFont-Bold.ttf"

    def fake_truetype(path_or_name, size, *args, **kwargs):
        calls.append(str(path_or_name))
        if str(path_or_name) == "DejaVuSans-Bold.ttf":
            raise OSError("named font missing")
        if str(path_or_name) == "/tmp/TestFont-Bold.ttf":
            return fallback_font
        raise OSError("unexpected font path")

    monkeypatch.setattr(image_stamp, "_FONT_PATH_CANDIDATES", {
        False: ("/tmp/TestFont-Regular.ttf",),
        True: ("/tmp/TestFont-Bold.ttf",),
    })
    monkeypatch.setattr("pathlib.Path.exists", fake_exists)

    with patch("app.services.image_stamp.ImageFont.truetype", side_effect=fake_truetype):
        font = image_stamp._load_font(36, bold=True)

    assert font is fallback_font
    assert calls == ["DejaVuSans-Bold.ttf", "/tmp/TestFont-Bold.ttf"]
