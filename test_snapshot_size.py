#!/usr/bin/env python3
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

        policy = json.loads(session.policy_snapshot_json) if session.policy_snapshot_json else {}
        runtime_timer = policy.get("runtime_timer", {})

        print("=== RUNTIME_TIMER STRUCTURE ===")
        print(f"Fields: {list(runtime_timer.keys())}")
        print(f"\nFull runtime_timer JSON size: {len(json.dumps(runtime_timer))} characters")
        print("\nFull runtime_timer:")
        print(json.dumps(runtime_timer, indent=2, ensure_ascii=False))

        snapshot = _build_live_snapshot_for_ai(session)
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)

        print("\n\n=== FULL LIVE_SESSION_SNAPSHOT (current implementation) ===")
        print(f"Total size: {len(snapshot_json)} characters")
        print(f"Total lines: {len(snapshot_json.splitlines())} lines")
        print("\nSnapshot preview (first 2000 chars):")
        print(snapshot_json[:2000])
        print("\n...\n")
        print("Snapshot tail (last 500 chars):")
        print(snapshot_json[-500:])

        estimated_tokens = len(snapshot_json) / 4
        print("\n=== TOKEN ESTIMATE ===")
        print(f"Estimated tokens for snapshot: ~{int(estimated_tokens)}")
        print("Current max_tokens for live requests: 2500")
        print(f"Estimated remaining tokens for AI response: ~{2500 - int(estimated_tokens)}")

        if 2500 - int(estimated_tokens) < 500:
            print("\nWARNING: Less than 500 tokens remaining for AI response.")
            print("Consider further reducing snapshot size or increasing max_tokens.")
        else:
            print("\nOK: Sufficient tokens remaining for comprehensive AI response.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
