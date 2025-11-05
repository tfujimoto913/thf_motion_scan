# Codex CLI Logout Procedure

Use the helper script to clear cached authentication tokens before switching accounts or handing a machine to another user. Pair this with the profile helper in `codex_profiles.md` when you regularly rotate between accounts.

```bash
python scripts/codex_logout.py
```

What happens:

- Creates `~/.codex/backups/auth.json.<timestamp>.bak` (skip with `--no-backup`).
- Deletes `~/.codex/auth.json`, forcing Codex CLI to request a fresh login next run.
- Prints a short status summary.

Optional flags:

- `--clear-sessions` removes cached session files under `~/.codex/sessions`.
- `--no-backup` disables the backup step (use with caution).

After running the script, Codex CLI will prompt for login/PKCE flow the next time it executes.
