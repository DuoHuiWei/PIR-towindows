from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import client_user_manager_log_path


@dataclass
class UserManagerLogEntry:
    admin_username: str
    admin_action: str
    target_username: str
    target_nickname: str
    action_time_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "admin_username": self.admin_username,
            "admin_action": self.admin_action,
            "target_username": self.target_username,
            "target_nickname": self.target_nickname,
            "action_time_utc": self.action_time_utc,
        }


def _load_existing_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"invalid user manager log format in {path}: expected JSON array")
    return payload


def write_user_manager_log(
    admin_username: str,
    admin_action: str,
    target_username: str,
    target_nickname: str,
) -> dict[str, Any]:
    clean_username = admin_username.strip() or "unknown"
    clean_action = admin_action.strip()
    clean_target_username = target_username.strip()
    clean_target_nickname = target_nickname.strip()
    if not clean_action:
        raise ValueError("admin_action is required")
    if not clean_target_username:
        raise ValueError("target_username is required")
    if not clean_target_nickname:
        raise ValueError("target_nickname is required")

    path = client_user_manager_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = UserManagerLogEntry(
        admin_username=clean_username,
        admin_action=clean_action,
        target_username=clean_target_username,
        target_nickname=clean_target_nickname,
        action_time_utc=datetime.now(timezone.utc).isoformat(),
    )

    entries = _load_existing_entries(path)
    entries.append(entry.to_dict())
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "log_path": path,
        "entry": entry.to_dict(),
    }


def list_user_manager_logs() -> list[dict[str, Any]]:
    path = client_user_manager_log_path()
    entries = _load_existing_entries(path)
    return list(reversed(entries))
