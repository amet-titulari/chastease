def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_simple_text_pdf(lines: list[str]) -> bytes:
    safe_lines = [line.encode("ascii", errors="replace").decode("ascii") for line in lines]
    if not safe_lines:
        safe_lines = ["(empty)"]

    y = 800
    text_ops = ["BT", "/F1 11 Tf", f"72 {y} Td"]
    first = True
    for line in safe_lines[:120]:
        escaped = _escape_pdf_text(line)
        if first:
            text_ops.append(f"({escaped}) Tj")
            first = False
        else:
            text_ops.append("0 -14 Td")
            text_ops.append(f"({escaped}) Tj")
    text_ops.append("ET")

    stream = "\n".join(text_ops).encode("ascii", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    )
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(
        b"5 0 obj\n<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n"
    )

    out = bytearray()
    out.extend(b"%PDF-1.4\n")

    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)

    xref_start = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    out.extend(
        (
            "trailer\n"
            f"<< /Size {len(offsets)} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_start}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    return bytes(out)
