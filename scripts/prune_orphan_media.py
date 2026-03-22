#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


TEXT_AFFINITIES = ("CHAR", "CLOB", "TEXT", "VARCHAR")
API_MEDIA_RE = re.compile(r"/api/media/(\d+)/content")
URL_MEDIA_RE = re.compile(r"/media/([^\s\"'\)]+)")


def _iter_text_columns(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    cur = conn.cursor()
    tables = [
        row["name"]
        for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    ]
    result: list[tuple[str, str]] = []
    for table in tables:
        cols = list(cur.execute(f"PRAGMA table_info({table})"))
        text_cols = [
            col["name"]
            for col in cols
            if any(affinity in (col["type"] or "").upper() for affinity in TEXT_AFFINITIES)
        ]
        result.extend((table, col) for col in text_cols)
    return result


def _media_id_map(conn: sqlite3.Connection) -> dict[int, str]:
    cur = conn.cursor()
    mapping: dict[int, str] = {}
    try:
        for row in cur.execute("SELECT id, storage_path FROM media_assets WHERE storage_path IS NOT NULL"):
            storage_path = str(row["storage_path"] or "").strip().lstrip("/")
            if storage_path:
                mapping[int(row["id"])] = storage_path
    except sqlite3.DatabaseError:
        return {}
    return mapping


def _extract_refs(raw: object, media_id_to_path: dict[int, str]) -> set[str]:
    if raw is None:
        return set()
    value = str(raw).strip()
    if not value:
        return set()

    refs: set[str] = set()

    if not value.startswith("/") and not value.startswith("http") and "data/media/" not in value:
        relative = value.lstrip("./")
        if "/" in relative:
            refs.add(relative)

    marker = "data/media/"
    idx = value.find(marker)
    while idx >= 0:
        tail = value[idx + len(marker):]
        match = re.match(r"([^\s\"']+)", tail)
        if match:
            refs.add(match.group(1))
        idx = value.find(marker, idx + len(marker))

    for match in URL_MEDIA_RE.finditer(value):
        refs.add(match.group(1))

    for match in API_MEDIA_RE.finditer(value):
        resolved = media_id_to_path.get(int(match.group(1)))
        if resolved:
            refs.add(resolved)

    return refs


def collect_referenced_media(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        media_id_to_path = _media_id_map(conn)
        refs: set[str] = set()
        cur = conn.cursor()
        for table, col in _iter_text_columns(conn):
            try:
                for row in cur.execute(f"SELECT {col} AS v FROM {table} WHERE {col} IS NOT NULL"):
                    refs.update(_extract_refs(row["v"], media_id_to_path))
            except sqlite3.DatabaseError:
                continue
        return refs
    finally:
        conn.close()


def collect_orphan_files(db_path: Path, media_dir: Path) -> tuple[list[Path], set[str]]:
    refs = collect_referenced_media(db_path)
    all_files = sorted(path for path in media_dir.rglob("*") if path.is_file())
    orphans = [
        path
        for path in all_files
        if str(path.resolve().relative_to(media_dir.resolve())).replace("\\", "/") not in refs
    ]
    return orphans, refs


def prune_orphan_files(media_dir: Path, orphans: list[Path]) -> None:
    for path in orphans:
        path.unlink(missing_ok=True)
    for path in sorted((p for p in media_dir.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Find and optionally delete files in media_dir that are no longer referenced in the SQLite database.")
    parser.add_argument("--db", default="data/chastease.db", help="Path to the SQLite database file.")
    parser.add_argument("--media-dir", default="data/media", help="Path to the media directory.")
    parser.add_argument("--delete", action="store_true", help="Actually delete orphaned files. Default is dry-run.")
    parser.add_argument("--limit", type=int, default=50, help="How many orphan paths to print.")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    media_dir = Path(args.media_dir).resolve()

    if not db_path.is_file():
        raise SystemExit(f"Database not found: {db_path}")
    if not media_dir.is_dir():
        raise SystemExit(f"Media directory not found: {media_dir}")

    orphans, refs = collect_orphan_files(db_path, media_dir)
    mode = "delete" if args.delete else "dry-run"
    print(f"mode={mode}")
    print(f"db={db_path}")
    print(f"media_dir={media_dir}")
    print(f"referenced_entries={len(refs)}")
    print(f"orphans={len(orphans)}")
    for item in orphans[: max(0, args.limit)]:
        print(item.resolve().relative_to(media_dir))

    if args.delete and orphans:
        prune_orphan_files(media_dir, orphans)
        print(f"deleted={len(orphans)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
