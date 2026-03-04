#!/usr/bin/env python3
"""
Manual script to demonstrate the difference between 'light' and 'full' detail levels.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "src"))

    from chastease.config import Config
    from chastease.db import build_engine, build_session_factory
    from chastease.models import ChastitySession
    from chastease.services.narration import _build_live_snapshot_for_ai

    config = Config()
    engine = build_engine(config.DATABASE_URL)
    session_factory = build_session_factory(engine)
    db = session_factory()

    session_id = "bdceef01-349f-4b1f-ada1-d452e3b9628a"
    try:
        session = db.get(ChastitySession, session_id)
        if not session:
            print(f"Session {session_id} not found")
            return 1

        print("=" * 80)
        print("LIGHT MODE (default - minimal token usage)")
        print("=" * 80)
        light_snapshot = _build_live_snapshot_for_ai(session, mode="light")
        light_json = json.dumps(light_snapshot, ensure_ascii=False, indent=2)
        print(light_json)
        print(f"\nSize: {len(light_json)} chars (~{len(light_json) // 4} tokens)")
        print(f"Fields: {list(light_snapshot.keys())}")

        print("\n" + "=" * 80)
        print("FULL MODE (includes psychogram & setup)")
        print("=" * 80)
        full_snapshot = _build_live_snapshot_for_ai(session, mode="full")
        full_json = json.dumps(full_snapshot, ensure_ascii=False, indent=2)
        print(full_json)
        print(f"\nSize: {len(full_json)} chars (~{len(full_json) // 4} tokens)")
        print(f"Fields: {list(full_snapshot.keys())}")

        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)
        print(f"Light mode: {len(light_json)} chars (~{len(light_json) // 4} tokens)")
        print(f"Full mode:  {len(full_json)} chars (~{len(full_json) // 4} tokens)")
        print(f"Difference: {len(full_json) - len(light_json)} chars (~{(len(full_json) - len(light_json)) // 4} tokens)")
        print(f"\nToken savings with light mode: ~{100 * (1 - len(light_json) / len(full_json)):.1f}%")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
