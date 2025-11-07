#!/usr/bin/env python3
"""Manage Codex CLI login profiles stored under ~/.codex/profiles."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List


CODEX_DIR = Path.home() / ".codex"
AUTH_FILE = CODEX_DIR / "auth.json"
PROFILES_DIR = CODEX_DIR / "profiles"
BACKUP_DIR = CODEX_DIR / "backups"
SESSIONS_DIR = CODEX_DIR / "sessions"

PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")


@dataclass
class ProfileInfo:
    name: str
    path: Path
    modified_at: datetime
    size: int


def ensure_codex_dir() -> None:
    if not CODEX_DIR.exists():
        raise SystemExit(
            f"No Codex directory found at {CODEX_DIR}. Run Codex CLI at least once first."
        )


def sanitized_name(name: str) -> str:
    if not PROFILE_NAME_PATTERN.match(name):
        raise SystemExit(
            "Invalid profile name. Use 1-64 characters: letters, digits, underscores, hyphens."
        )
    return name


def profiles_dir() -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR


def iter_profiles() -> Iterable[ProfileInfo]:
    directory = profiles_dir()
    for entry in sorted(directory.glob("*.json")):
        stat = entry.stat()
        yield ProfileInfo(
            name=entry.stem,
            path=entry,
            modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
            size=stat.st_size,
        )


def backup_auth() -> Path | None:
    if not AUTH_FILE.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"auth.json.{timestamp}.bak"
    shutil.copy2(AUTH_FILE, backup_path)
    return backup_path


def remove_sessions() -> int:
    if not SESSIONS_DIR.exists():
        return 0

    removed = 0
    for file_path in SESSIONS_DIR.rglob("*"):
        if file_path.is_file():
            file_path.unlink(missing_ok=True)
            removed += 1

    # clean empty dirs
    for dir_path in sorted(SESSIONS_DIR.rglob("*"), reverse=True):
        if dir_path.is_dir():
            try:
                dir_path.rmdir()
            except OSError:
                pass

    return removed


def load_account_id(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return None

    tokens = data.get("tokens")
    if isinstance(tokens, dict):
        account = tokens.get("account_id")
        if isinstance(account, str) and account:
            return account
    return None


def require_auth_file() -> None:
    if not AUTH_FILE.exists():
        raise SystemExit(f"No auth.json found at {AUTH_FILE}. Log in once before saving profiles.")


def cmd_list(_: argparse.Namespace) -> None:
    rows: List[str] = []
    for profile in iter_profiles():
        account = load_account_id(profile.path)
        account_repr = account if account else "-"
        rows.append(
            f"{profile.name:<16} {profile.size:>6} bytes  "
            f"modified {profile.modified_at.isoformat()}  account:{account_repr}"
        )

    if rows:
        print("Available Codex profiles:")
        for line in rows:
            print("  ", line)
    else:
        print("No Codex profiles found. Use 'save' to capture the current login state.")


def cmd_save(args: argparse.Namespace) -> None:
    ensure_codex_dir()
    require_auth_file()
    name = sanitized_name(args.name)
    profiles_directory = profiles_dir()
    dest = profiles_directory / f"{name}.json"

    if dest.exists() and not args.overwrite:
        raise SystemExit(
            f"Profile '{name}' already exists at {dest}. Use --overwrite to replace it."
        )

    shutil.copy2(AUTH_FILE, dest)
    account = load_account_id(dest)
    print(f"Saved current auth.json to {dest}")
    if account:
        print(f"  account_id: {account}")


def cmd_apply(args: argparse.Namespace) -> None:
    ensure_codex_dir()
    name = sanitized_name(args.name)
    profile_path = profiles_dir() / f"{name}.json"
    if not profile_path.exists():
        raise SystemExit(f"Profile '{name}' not found at {profile_path}")

    if not args.no_backup:
        backup_path = backup_auth()
        if backup_path:
            print(f"Backup created: {backup_path}")

    shutil.copy2(profile_path, AUTH_FILE)
    print(f"Applied profile '{name}' -> {AUTH_FILE}")

    if args.clear_sessions:
        removed = remove_sessions()
        if removed:
            print(f"Removed {removed} session file(s).")
        else:
            print("No session files found.")

    account = load_account_id(AUTH_FILE)
    if account:
        print(f"  active account_id: {account}")


def cmd_delete(args: argparse.Namespace) -> None:
    ensure_codex_dir()
    name = sanitized_name(args.name)
    profile_path = profiles_dir() / f"{name}.json"
    if not profile_path.exists():
        raise SystemExit(f"Profile '{name}' not found.")

    if not args.force:
        confirm = input(f"Delete profile '{name}' at {profile_path}? [y/N]: ").strip().lower()
        if confirm not in {"y", "yes"}:
            print("Aborted.")
            return

    profile_path.unlink()
    print(f"Deleted profile '{name}'.")


def cmd_show(args: argparse.Namespace) -> None:
    ensure_codex_dir()
    target: Path
    if args.name:
        name = sanitized_name(args.name)
        target = profiles_dir() / f"{name}.json"
    else:
        target = AUTH_FILE

    if not target.exists():
        raise SystemExit(f"File not found: {target}")

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise SystemExit(f"Invalid JSON in {target}")

    tokens = data.get("tokens", {})
    account = tokens.get("account_id")
    expiry = tokens.get("expires_at") or tokens.get("expiry")
    print(f"Details for {target}:")
    print(f"  account_id : {account or '-'}")
    print(f"  expires_at : {expiry or '-'}")
    print(f"  has_access : {'access_token' in tokens}")
    print(f"  has_refresh: {'refresh_token' in tokens}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Codex CLI authentication profiles."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cmd = sub.add_parser("list", help="List saved login profiles.")
    cmd.set_defaults(func=cmd_list)

    cmd = sub.add_parser("save", help="Save the current auth.json as a named profile.")
    cmd.add_argument("name", help="Profile name (letters, digits, underscore, hyphen).")
    cmd.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite profile if it already exists.",
    )
    cmd.set_defaults(func=cmd_save)

    cmd = sub.add_parser("apply", help="Replace auth.json with a saved profile.")
    cmd.add_argument("name", help="Profile name to activate.")
    cmd.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating auth.json backup before applying.",
    )
    cmd.add_argument(
        "--clear-sessions",
        action="store_true",
        help="Remove cached session files under ~/.codex/sessions.",
    )
    cmd.set_defaults(func=cmd_apply)

    cmd = sub.add_parser("delete", help="Delete a saved profile.")
    cmd.add_argument("name", help="Profile name to remove.")
    cmd.add_argument(
        "--force",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    cmd.set_defaults(func=cmd_delete)

    cmd = sub.add_parser(
        "show", help="Show metadata for auth.json or a specific profile."
    )
    cmd.add_argument(
        "name",
        nargs="?",
        help="Profile name. If omitted, show details for the active auth.json.",
    )
    cmd.set_defaults(func=cmd_show)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
