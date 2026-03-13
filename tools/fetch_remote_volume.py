#!/usr/bin/env python3
"""Fetch app data from a remote docker volume via scp.

Supports two modes:
- all: fetch full data directory
- db-only: fetch only database file
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

#defaultMode="db-only"
defaultMode="all"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch remote app data using scp with optional safety backups.",
    )
    parser.add_argument("--user", default="root", help="Remote SSH user (default: root)")
    parser.add_argument("--host", default="65.108.149.214", help="Remote host")
    parser.add_argument(
        "--remote-path",
        default="/var/lib/docker/volumes/chastease_chastease_data",
        help="Remote docker volume path",
    )
    parser.add_argument(
        "--remote-data-subdir",
        default="_data",
        help="Subdirectory inside the docker volume that stores app data (default: _data)",
    )
    parser.add_argument(
        "--local-dir",
        default="./data",
        help="Local target directory (default: ./data)",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "db-only"),
        default=defaultMode,
        help="all = copy full data dir, db-only = copy only DB file",
    )
    parser.add_argument(
        "--db-filename",
        default="chastease.db",
        help="Database filename for db-only mode (default: chastease.db)",
    )
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument(
        "--identity-file",
        default=None,
        help="Optional SSH private key file",
    )
    parser.add_argument(
        "--backup-dir",
        default="./backups",
        help="Directory for ZIP backups before overwrite (default: ./backups)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Disable automatic ZIP backup before overwrite",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without executing them",
    )
    return parser


def run_scp(
    *,
    user: str,
    host: str,
    remote_path: str,
    local_path: Path,
    recursive: bool,
    port: int,
    identity_file: str | None,
    dry_run: bool,
) -> int:
    cmd: list[str] = ["scp", "-P", str(port)]
    if recursive:
        cmd.append("-r")
    if identity_file:
        cmd.extend(["-i", str(Path(identity_file).expanduser())])
    cmd.extend([f"{user}@{host}:{remote_path}", str(local_path)])

    print("Running:", " ".join(cmd))
    if dry_run:
        return 0

    try:
        subprocess.run(cmd, check=True)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"scp failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode


def zip_directory(src_dir: Path, backup_dir: Path, prefix: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = backup_dir / f"{prefix}_{stamp}"
    archive_path = shutil.make_archive(str(base_name), "zip", root_dir=src_dir.parent, base_dir=src_dir.name)
    return Path(archive_path)


def zip_single_file(src_file: Path, backup_dir: Path, prefix: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = backup_dir / f"{prefix}_{stamp}.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.write(src_file, arcname=src_file.name)
    return zip_path


def merge_tree(src_dir: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src in src_dir.iterdir():
        dst = dst_dir / src.name
        if src.is_dir():
            if dst.exists() and dst.is_file():
                dst.unlink()
            if not dst.exists():
                shutil.copytree(src, dst)
            else:
                merge_tree(src, dst)
            continue

        if dst.exists() and dst.is_dir():
            shutil.rmtree(dst)
        shutil.copy2(src, dst)


def main() -> int:
    args = build_parser().parse_args()

    if shutil.which("scp") is None:
        print("Error: 'scp' not found in PATH.", file=sys.stderr)
        return 127

    local_dir = Path(args.local_dir).expanduser().resolve()
    local_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(args.backup_dir).expanduser().resolve()

    remote_base = args.remote_path.rstrip("/")
    remote_data_root = f"{remote_base}/{args.remote_data_subdir.strip('/')}" if args.remote_data_subdir else remote_base

    # Backup before overwrite for safer restore.
    if not args.no_backup:
        if args.mode == "all":
            has_existing_content = local_dir.exists() and any(local_dir.iterdir())
            if has_existing_content:
                if args.dry_run:
                    print(f"Backup (dry-run): would zip directory {local_dir} into {backup_dir}")
                else:
                    archive = zip_directory(local_dir, backup_dir, "data_backup")
                    print(f"Backup created: {archive}")
        else:
            db_path = local_dir / args.db_filename
            if db_path.exists():
                if args.dry_run:
                    print(f"Backup (dry-run): would zip file {db_path} into {backup_dir}")
                else:
                    archive = zip_single_file(db_path, backup_dir, "db_backup")
                    print(f"Backup created: {archive}")

    if args.mode == "db-only":
        with tempfile.TemporaryDirectory(prefix="chastease_db_fetch_") as tmp:
            tmp_path = Path(tmp)
            rc = run_scp(
                user=args.user,
                host=args.host,
                remote_path=f"{remote_data_root}/{args.db_filename}",
                local_path=tmp_path,
                recursive=False,
                port=args.port,
                identity_file=args.identity_file,
                dry_run=args.dry_run,
            )
            if rc != 0 or args.dry_run:
                return rc

            fetched_db = tmp_path / args.db_filename
            if not fetched_db.exists():
                print(f"Error: expected fetched file not found: {fetched_db}", file=sys.stderr)
                return 2

            target_db = local_dir / args.db_filename
            shutil.copy2(fetched_db, target_db)
            print(f"Database updated: {target_db}")
            return 0

    with tempfile.TemporaryDirectory(prefix="chastease_all_fetch_") as tmp:
        tmp_path = Path(tmp)
        rc = run_scp(
            user=args.user,
            host=args.host,
            remote_path=remote_data_root,
            local_path=tmp_path,
            recursive=True,
            port=args.port,
            identity_file=args.identity_file,
            dry_run=args.dry_run,
        )
        if rc != 0 or args.dry_run:
            return rc

        fetched_root = tmp_path / Path(remote_data_root).name
        if not fetched_root.exists() or not fetched_root.is_dir():
            print(f"Error: expected fetched directory not found: {fetched_root}", file=sys.stderr)
            return 2

        merge_tree(fetched_root, local_dir)
        print(f"Data synchronized into: {local_dir}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
