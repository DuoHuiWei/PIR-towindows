from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import client_database_log_path


@dataclass
class DatabaseLogEntry:
    db_name: str
    db_action: str
    action_time_utc: str
    action_result: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_name": self.db_name,
            "db_action": self.db_action,
            "action_time_utc": self.action_time_utc,
            "action_result": self.action_result,
        }


def _load_existing_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"invalid database log format in {path}: expected JSON array")
    return payload


def write_database_log(db_name: str, db_action: str, action_result: str) -> dict[str, Any]:
    clean_db_name = db_name.strip()
    clean_action = db_action.strip()
    clean_result = action_result.strip()
    if not clean_db_name:
        raise ValueError("db_name is required")
    if not clean_action:
        raise ValueError("db_action is required")
    if not clean_result:
        raise ValueError("action_result is required")

    path = client_database_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = DatabaseLogEntry(
        db_name=clean_db_name,
        db_action=clean_action,
        action_time_utc=datetime.now(timezone.utc).isoformat(),
        action_result=clean_result,
    )

    entries = _load_existing_entries(path)
    entries.append(entry.to_dict())
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "log_path": path,
        "entry": entry.to_dict(),
    }


def list_database_logs() -> list[dict[str, Any]]:
    path = client_database_log_path()
    entries = _load_existing_entries(path)
    return list(reversed(entries))
