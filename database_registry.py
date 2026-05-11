from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from config import WORKSPACE_ROOT


CLIENT_DB_PATH = WORKSPACE_ROOT / "client_db.json"
SERVER_DB_PATH = WORKSPACE_ROOT / "sever_db.json"
VALID_PREP_STATUS = {"未完成", "pirex", "pirexx", "pirex+pirexx"}

_REGISTRY_LOCK = Lock()


def _default_payload() -> dict[str, list[dict[str, Any]]]:
    return {"databases": []}


def _ensure_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(json.dumps(_default_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_payload(path: Path) -> dict[str, Any]:
    _ensure_registry(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_prep_status(prep_status: str) -> str:
    status = prep_status.strip() or "未完成"
    if status not in VALID_PREP_STATUS:
        raise ValueError(f"invalid prep_status: {status}")
    return status


def merge_prep_status(current_status: str, scheme: str) -> str:
    current = normalize_prep_status(current_status)
    target = normalize_prep_status(scheme)

    if target == "未完成":
        return current
    if current == "未完成":
        return target
    if current == target:
        return current
    if {current, target} == {"pirex", "pirexx"}:
        return "pirex+pirexx"
    if current == "pirex+pirexx" or target == "pirex+pirexx":
        return "pirex+pirexx"
    return target


def remove_prep_status(current_status: str, scheme: str) -> str:
    current = normalize_prep_status(current_status)
    target = normalize_prep_status(scheme)

    if target == "未完成":
        return current
    if current == "未完成":
        return current
    if current == target:
        return "未完成"
    if current == "pirex+pirexx":
        if target == "pirex":
            return "pirexx"
        if target == "pirexx":
            return "pirex"
    return current


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    raw_prep_status = str(entry.get("prep_status", "未完成")).strip() or "未完成"
    prep_status = raw_prep_status if raw_prep_status in VALID_PREP_STATUS else "未完成"
    return {
        "db_name": str(entry.get("db_name", "")),
        "created_at_utc": str(entry.get("created_at_utc", "")),
        "file_count": int(entry.get("file_count", 0)),
        "total_size_bytes": int(entry.get("total_size_bytes", 0)),
        "prep_status": prep_status,
    }


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_entries(path: Path) -> list[dict[str, Any]]:
    payload = _read_payload(path)
    entries = [_normalize_entry(entry) for entry in payload.get("databases", [])]
    return sorted(entries, key=lambda item: item["db_name"])


def get_entry(path: Path, db_name: str) -> dict[str, Any] | None:
    target = db_name.strip()
    for entry in list_entries(path):
        if entry["db_name"] == target:
            return entry
    return None


def upsert_entry(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_entry(entry)
    if not normalized["db_name"]:
        raise ValueError("db_name is required")

    with _REGISTRY_LOCK:
        payload = _read_payload(path)
        entries = [_normalize_entry(item) for item in payload.get("databases", []) if item.get("db_name") != normalized["db_name"]]
        entries.append(normalized)
        payload["databases"] = sorted(entries, key=lambda item: item["db_name"])
        _write_payload(path, payload)
    return normalized


def create_entry(
    path: Path,
    db_name: str,
    *,
    created_at_utc: str | None = None,
    file_count: int = 0,
    total_size_bytes: int = 0,
    prep_status: str = "未完成",
) -> dict[str, Any]:
    name = db_name.strip()
    if not name:
        raise ValueError("db_name is required")
    if get_entry(path, name) is not None:
        raise FileExistsError(f"database already exists: {name}")
    return upsert_entry(
        path,
        {
            "db_name": name,
            "created_at_utc": created_at_utc or now_utc_iso(),
            "file_count": file_count,
            "total_size_bytes": total_size_bytes,
            "prep_status": normalize_prep_status(prep_status),
        },
    )


def replace_entry_stats(
    path: Path,
    db_name: str,
    *,
    file_count: int,
    total_size_bytes: int,
) -> dict[str, Any]:
    name = db_name.strip()
    with _REGISTRY_LOCK:
        payload = _read_payload(path)
        entries = payload.get("databases", [])
        updated = None
        for entry in entries:
            if str(entry.get("db_name", "")) == name:
                current = _normalize_entry(entry)
                current["file_count"] = max(0, int(file_count))
                current["total_size_bytes"] = max(0, int(total_size_bytes))
                entry.update(current)
                updated = current
                break
        if updated is None:
            raise FileNotFoundError(f"database not found: {name}")
        payload["databases"] = sorted([_normalize_entry(item) for item in entries], key=lambda item: item["db_name"])
        _write_payload(path, payload)
        return updated


def update_entry_stats(
    path: Path,
    db_name: str,
    *,
    file_count_delta: int = 0,
    total_size_delta: int = 0,
) -> dict[str, Any]:
    name = db_name.strip()
    with _REGISTRY_LOCK:
        payload = _read_payload(path)
        entries = payload.get("databases", [])
        updated = None
        for entry in entries:
            if str(entry.get("db_name", "")) == name:
                current = _normalize_entry(entry)
                current["file_count"] = max(0, current["file_count"] + int(file_count_delta))
                current["total_size_bytes"] = max(0, current["total_size_bytes"] + int(total_size_delta))
                entry.update(current)
                updated = current
                break
        if updated is None:
            raise FileNotFoundError(f"database not found: {name}")
        payload["databases"] = sorted([_normalize_entry(item) for item in entries], key=lambda item: item["db_name"])
        _write_payload(path, payload)
        return updated


def update_entry_prep_status(path: Path, db_name: str, prep_status: str) -> dict[str, Any]:
    name = db_name.strip()
    status = normalize_prep_status(prep_status)
    with _REGISTRY_LOCK:
        payload = _read_payload(path)
        entries = payload.get("databases", [])
        updated = None
        for entry in entries:
            if str(entry.get("db_name", "")) == name:
                current = _normalize_entry(entry)
                current["prep_status"] = status
                entry.update(current)
                updated = current
                break
        if updated is None:
            raise FileNotFoundError(f"database not found: {name}")
        payload["databases"] = sorted([_normalize_entry(item) for item in entries], key=lambda item: item["db_name"])
        _write_payload(path, payload)
        return updated


def delete_entry(path: Path, db_name: str) -> bool:
    name = db_name.strip()
    with _REGISTRY_LOCK:
        payload = _read_payload(path)
        entries = [_normalize_entry(entry) for entry in payload.get("databases", [])]
        remaining = [entry for entry in entries if entry["db_name"] != name]
        if len(remaining) == len(entries):
            raise FileNotFoundError(f"database not found: {name}")
        payload["databases"] = remaining
        _write_payload(path, payload)
    return True
