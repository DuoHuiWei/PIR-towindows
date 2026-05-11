from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import client_all_log_path


@dataclass
class AllLogEntry:
    query_user: str
    db_name: str
    query_time_utc: str
    time_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_user": self.query_user,
            "db_name": self.db_name,
            "query_time_utc": self.query_time_utc,
            "time_ms": self.time_ms,
        }


def _load_existing_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"invalid all_log format in {path}: expected JSON array")
    return payload


def write_all_log(query_user: str, db_name: str, time_ms: float) -> dict[str, Any]:
    path = client_all_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = AllLogEntry(
        query_user=query_user.strip() or "unknown",
        db_name=db_name,
        query_time_utc=datetime.now(timezone.utc).isoformat(),
        time_ms=round(time_ms, 4),
    )

    entries = _load_existing_entries(path)
    entries.append(entry.to_dict())
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "log_path": path,
        "entry": entry.to_dict(),
    }
