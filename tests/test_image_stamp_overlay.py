from app.services import image_stamp


class _FakeFont:
    def __init__(self, size: int) -> None:
        self.size = size


class _FakeDraw:
    def __init__(self) -> None:
        self.rounded_rectangles: list[dict] = []
        self.text_calls: list[dict] = []

    def textbbox(self, xy, text, font=None):
        size = getattr(font, "size", 16)
        width = max(1, int(len(str(text)) * size * 0.45))
        height = max(1, int(size))
        return (0, 0, width, height)

    def rounded_rectangle(self, coords, **kwargs):
        self.rounded_rectangles.append({"coords": coords, **kwargs})

    def text(self, xy, text, **kwargs):
        self.text_calls.append({"xy": xy, "text": text, **kwargs})


def test_top_overlay_uses_minimum_box_width_for_readability(monkeypatch):
    draw = _FakeDraw()

    monkeypatch.setattr(
        image_stamp,
        "_load_font",
        lambda size, bold=False: _FakeFont(size),
    )

    image_stamp._draw_text_box(
        draw,
        anchor="top-left",
        image_width=4032,
        image_height=3024,
        title="Gefordert",
        body="Kurzer Text",
    )

    assert draw.rounded_rectangles
    box = draw.rounded_rectangles[0]["coords"]
    assert box[2] - box[0] >= int(4032 * 0.16)
    assert draw.text_calls
