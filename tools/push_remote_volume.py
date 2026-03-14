#!/usr/bin/env python3
"""Push local app data to a remote docker volume via scp.

Supports two modes:
- all: push full local data directory
- db-only: push only database file
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

#defaultMode = "all"
defaultMode = "db-only"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Push local app data to remote host using scp with optional safety backup.",
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
        help="Local source directory (default: ./data)",
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
        "--remote-backup",
        action="store_true",
        help="Create a timestamped copy of remote target before overwrite",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without executing them",
    )
    return parser


def run_cmd(cmd: list[str], *, dry_run: bool) -> int:
    print("Running:", " ".join(cmd))
    if dry_run:
        return 0
    try:
        subprocess.run(cmd, check=True)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode


def build_ssh_cmd(port: int, identity_file: str | None, remote_command: str, user: str, host: str) -> list[str]:
    cmd = ["ssh", "-p", str(port)]
    if identity_file:
        cmd.extend(["-i", str(Path(identity_file).expanduser())])
    cmd.extend([f"{user}@{host}", remote_command])
    return cmd


def build_scp_cmd(port: int, identity_file: str | None, src: str, dst: str, recursive: bool) -> list[str]:
    cmd = ["scp", "-P", str(port)]
    if recursive:
        cmd.append("-r")
    if identity_file:
        cmd.extend(["-i", str(Path(identity_file).expanduser())])
    cmd.extend([src, dst])
    return cmd


def remote_backup_target(
    *,
    user: str,
    host: str,
    port: int,
    identity_file: str | None,
    remote_target: str,
    dry_run: bool,
) -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{remote_target}.backup_{stamp}"
    # Use cp -a to preserve metadata while creating a rollback copy.
    remote_cmd = f"if [ -e '{remote_target}' ]; then cp -a '{remote_target}' '{backup_path}'; fi"
    cmd = build_ssh_cmd(port, identity_file, remote_cmd, user, host)
    rc = run_cmd(cmd, dry_run=dry_run)
    if rc == 0:
        print(f"Remote backup ready: {backup_path}")
    return rc


def main() -> int:
    args = build_parser().parse_args()

    if shutil.which("scp") is None:
        print("Error: 'scp' not found in PATH.", file=sys.stderr)
        return 127
    if args.remote_backup and shutil.which("ssh") is None:
        print("Error: 'ssh' not found in PATH (required for --remote-backup).", file=sys.stderr)
        return 127

    local_dir = Path(args.local_dir).expanduser().resolve()
    remote_base = args.remote_path.rstrip("/")
    remote_data_root = f"{remote_base}/{args.remote_data_subdir.strip('/')}" if args.remote_data_subdir else remote_base

    if args.mode == "db-only":
        local_db = local_dir / args.db_filename
        if not local_db.exists():
            print(f"Error: local DB file not found: {local_db}", file=sys.stderr)
            return 2

        remote_target = f"{remote_data_root}/{args.db_filename}"
        if args.remote_backup:
            rc = remote_backup_target(
                user=args.user,
                host=args.host,
                port=args.port,
                identity_file=args.identity_file,
                remote_target=remote_target,
                dry_run=args.dry_run,
            )
            if rc != 0:
                return rc

        scp_cmd = build_scp_cmd(
            args.port,
            args.identity_file,
            str(local_db),
            f"{args.user}@{args.host}:{remote_target}",
            False,
        )
        rc = run_cmd(scp_cmd, dry_run=args.dry_run)
        if rc == 0:
            print(f"Remote DB updated: {remote_target}")
        return rc

    if not local_dir.exists() or not local_dir.is_dir():
        print(f"Error: local directory not found: {local_dir}", file=sys.stderr)
        return 2

    remote_target = remote_data_root
    if args.remote_backup:
        rc = remote_backup_target(
            user=args.user,
            host=args.host,
            port=args.port,
            identity_file=args.identity_file,
            remote_target=remote_target,
            dry_run=args.dry_run,
        )
        if rc != 0:
            return rc

    # Copy directory contents to remote target while keeping directory name stable.
    src = f"{str(local_dir).rstrip('/')}/."
    scp_cmd = build_scp_cmd(
        args.port,
        args.identity_file,
        src,
        f"{args.user}@{args.host}:{remote_target}",
        True,
    )
    rc = run_cmd(scp_cmd, dry_run=args.dry_run)
    if rc == 0:
        print(f"Remote data synchronized into: {remote_target}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
