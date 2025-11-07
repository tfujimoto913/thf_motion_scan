# Codex CLI Login Profiles

Codex stores authentication tokens in `~/.codex/auth.json`.  
Use `scripts/codex_profiles.py` to capture that file as reusable profiles and swap between accounts quickly.

```bash
# List profiles
python scripts/codex_profiles.py list

# Save current login into a profile (first run requires manual login)
python scripts/codex_profiles.py save dev

# Activate a profile (creates ~/.codex/backups/auth.json.<timestamp>.bak by default)
python scripts/codex_profiles.py apply prod

# Remove a profile
python scripts/codex_profiles.py delete dev
```

Tips:

- Profiles live under `~/.codex/profiles/<name>.json`. Guard this directory because it contains reusable refresh/access tokens.
- `apply --clear-sessions` clears cached data under `~/.codex/sessions` to avoid accidental reuse of the previous login.
- `save --overwrite` lets you refresh a profile after re-authenticating it.
- Combine with `scripts/codex_logout.py` when you need a clean slate (`apply` already accepts `--no-backup` if you do not want the safety copy).
