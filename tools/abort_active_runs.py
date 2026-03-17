"""
abort_active_runs.py
====================
Beendet alle aktiven GameRuns in der lokalen Datenbank (chastease.db).
Nützlich beim Testen, wenn ein Spiel im Status "active" hängengeblieben ist.

Usage:
    python tools/abort_active_runs.py
    python tools/abort_active_runs.py --db-path data/chastease.db
    python tools/abort_active_runs.py --dry-run
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.game_run import GameRun
from app.models.game_run_step import GameRunStep
from app.models.message import Message


def main() -> None:
    parser = argparse.ArgumentParser(description="Alle aktiven GameRuns beenden.")
    parser.add_argument(
        "--db-path",
        default=None,
        help="Pfad zur SQLite-Datenbankdatei (überschreibt CHASTEASE_DATABASE_URL).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Zeigt nur an, was beendet würde, ohne Änderungen zu schreiben.",
    )
    args = parser.parse_args()

    if args.db_path:
        os.environ["CHASTEASE_DATABASE_URL"] = f"sqlite:///{args.db_path}"

    db = SessionLocal()
    try:
        runs = db.query(GameRun).filter(GameRun.status == "active").all()

        if not runs:
            print("Keine aktiven Spiele gefunden.")
            return

        print(f"{'[DRY-RUN] ' if args.dry_run else ''}Gefundene aktive Spiele: {len(runs)}")

        now = datetime.now(timezone.utc)
        for run in runs:
            steps = db.query(GameRunStep).filter(GameRunStep.run_id == run.id).all()
            passed = sum(1 for s in steps if s.status == "passed")
            failed = sum(1 for s in steps if s.status == "failed")
            unplayed = sum(1 for s in steps if s.status == "pending")

            print(
                f"  Run ID={run.id}  module={run.module_key}  session={run.session_id}"
                f"  started={run.started_at}"
                f"  passed={passed}  failed={failed}  unplayed={unplayed}"
                f"  misses={run.miss_count}"
            )

            if args.dry_run:
                continue

            existing_meta: dict = {}
            if run.summary_json:
                try:
                    existing_meta = json.loads(run.summary_json)
                except Exception:
                    pass
            checks = existing_meta.get("checks", []) if isinstance(existing_meta, dict) else []

            summary = {
                "end_reason": "manually_aborted",
                "total_steps": passed + failed,
                "played_steps": passed + failed,
                "scheduled_steps": len(steps),
                "unplayed_steps": unplayed,
                "passed_steps": passed,
                "failed_steps": failed,
                "timeout_failed_steps": 0,
                "miss_count": run.miss_count,
                "retry_extension_seconds": run.retry_extension_seconds,
                "session_penalty_applied": bool(run.session_penalty_applied),
                "scheduled_duration_seconds": int(run.total_duration_seconds),
                "checks": checks,
            }
            run.status = "completed"
            run.finished_at = now
            run.summary_json = json.dumps(summary, ensure_ascii=True)

            db.add(Message(
                session_id=run.session_id,
                role="system",
                message_type="game_report",
                content=(
                    f"Spiel {run.module_key} manuell abgebrochen: "
                    f"passed={passed}, failed={failed}, unplayed={unplayed}, misses={run.miss_count}"
                ),
            ))
            db.add(run)

        if not args.dry_run:
            db.commit()
            print(f"\n{len(runs)} Spiel(e) erfolgreich beendet.")
        else:
            print("\n[DRY-RUN] Keine Änderungen geschrieben.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
