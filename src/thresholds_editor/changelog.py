"""Change log entry representation for threshold updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from .preview import RepresentativeSample


@dataclass
class ChangeLogEntry:
    id: str
    actor: str
    env: str
    test: str
    metric: str
    prev: Dict[str, List[float]]
    next: Dict[str, List[float]]
    reclassified_rate: float
    reclassified_count: int
    sample_n: int
    representatives: Dict[str, List[str]]
    versions: Dict[str, str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_preview(
        cls,
        *,
        actor: str,
        env: str,
        test: str,
        metric: str,
        prev: Dict[str, List[float]],
        nxt: Dict[str, List[float]],
        sample_records: int,
        preview_representatives: Dict[str, Iterable[RepresentativeSample]],
        reclassified_rate: float,
        reclassified_count: int,
        versions: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> "ChangeLogEntry":
        ts = timestamp or datetime.now(timezone.utc)
        entry_id = f"chg_{ts.isoformat()}"
        representatives = {
            key: [sample.rep_id for sample in preview_representatives.get(key, [])]
            for key in ("upshift", "downshift")
        }
        return cls(
            id=entry_id,
            actor=actor,
            env=env,
            test=test,
            metric=metric,
            prev=prev,
            next=nxt,
            reclassified_rate=reclassified_rate,
            reclassified_count=reclassified_count,
            sample_n=sample_records,
            representatives=representatives,
            versions=versions or {},
            timestamp=ts,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "actor": self.actor,
            "env": self.env,
            "test": self.test,
            "metric": self.metric,
            "prev": self.prev,
            "next": self.next,
            "reclassified_rate": round(self.reclassified_rate, 4),
            "reclassified_count": self.reclassified_count,
            "sample_n": self.sample_n,
            "representatives": self.representatives,
            "versions": self.versions,
            "timestamp": self.timestamp.isoformat(),
        }

def log_undo(actor, env, rollback_of_id, reverted_snapshot_path):
    """直前の変更をロールバックした時のログエントリを追記する。"""
    entry = {
        "id": iso_now_id(),
        "actor": actor,
        "env": env,
        "action": "undo",
        "rollback_of": rollback_of_id,
        "reverted_snapshot": reverted_snapshot_path,
        "timestamp": iso_now(),
    }
    append_jsonl("config/thresholds/changelog.jsonl", entry)
    return entry

from datetime import datetime, timezone

def iso_now():
    """UTC ISO8601 タイムスタンプを返す"""
    return datetime.now(timezone.utc).isoformat()

def iso_now_id():
    """変更IDを生成（chg_ + ISO8601）"""
    return "chg_" + datetime.now(timezone.utc).isoformat().replace(":", "").replace(".", "")

from pathlib import Path
import json
import logging

def append_jsonl(path: str, record: dict):
    """JSON Lines 形式でログを1行追加する（ファイルが無ければ作成）"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logging.info({"event": "append_jsonl", "func": "append_jsonl", "status": "ok"})
