#!/usr/bin/env python3
"""Clear Codex CLI authentication tokens to simulate a logout."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


CODEX_DIR = Path.home() / ".codex"
AUTH_FILE = CODEX_DIR / "auth.json"
SESSIONS_DIR = CODEX_DIR / "sessions"
BACKUP_DIR = CODEX_DIR / "backups"


def backup_auth_file() -> Path | None:
    """Create a timestamped backup of auth.json, returning the backup path."""
    if not AUTH_FILE.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"auth.json.{timestamp}.bak"
    try:
        shutil.copy2(AUTH_FILE, backup_path)
    except PermissionError as exc:
        raise SystemExit(
            f"Failed to write backup at {backup_path}: {exc}\n"
            "Retry with --no-backup if you don't need a safety copy."
        ) from exc
    return backup_path


def clear_auth_file() -> None:
    """Remove auth.json entirely so the CLI re-runs the login flow."""
    if not AUTH_FILE.exists():
        print("No auth.json found; nothing to clear.")
        return

    AUTH_FILE.unlink(missing_ok=True)
    print(f"Deleted {AUTH_FILE}")


def remove_sessions() -> list[Path]:
    """Delete per-session files to prevent reuse of cached sessions."""
    removed: list[Path] = []
    if not SESSIONS_DIR.exists():
        return removed

    for path in SESSIONS_DIR.rglob("*"):
        if path.is_file():
            path.unlink(missing_ok=True)
            removed.append(path)

    # Clean up empty directories
    for path in sorted(SESSIONS_DIR.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass

    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove Codex CLI authentication tokens (logout)."
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup of auth.json before clearing it.",
    )
    parser.add_argument(
        "--clear-sessions",
        action="store_true",
        help="Also delete cached sessions under ~/.codex/sessions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not CODEX_DIR.exists():
        print("Codex directory not found; nothing to do.")
        return 0

    backup_path = None
    if not args.no_backup:
        backup_path = backup_auth_file()
        if backup_path:
            print(f"Backup created: {backup_path}")

    clear_auth_file()

    if args.clear_sessions:
        removed_files = remove_sessions()
        if removed_files:
            print(f"Removed {len(removed_files)} session file(s).")
        else:
            print("No session files found to remove.")

    print("Codex logout complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
