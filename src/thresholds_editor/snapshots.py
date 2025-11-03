"""Snapshot helpers for threshold rollback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional


def snapshot_thresholds(
    thresholds_path: Path,
    output_dir: Path,
    *,
    timestamp: Optional[datetime] = None,
) -> Path:
    if not thresholds_path.exists():
        raise FileNotFoundError(thresholds_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = (timestamp or datetime.now(timezone.utc)).replace(microsecond=0)
    dest = output_dir / f"thresholds-{ts.isoformat().replace(':', '-')}.json"
    dest.write_text(thresholds_path.read_text(encoding="utf-8"), encoding="utf-8")
    return dest
