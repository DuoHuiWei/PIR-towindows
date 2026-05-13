from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import client_query_log_path


_CLIENT_ACCESS_PATTERN = re.compile(r"client access done in ([0-9.]+)(ns|us|µs|碌s|纰宻|ms|s)")


@dataclass
class QueryLogEntry:
    query_username: str
    db_name: str
    file_name: str
    download_action: str
    query_time_utc: str
    download_result: str
    avg_block_query_time_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_username": self.query_username,
            "db_name": self.db_name,
            "file_name": self.file_name,
            "download_action": self.download_action,
            "query_time_utc": self.query_time_utc,
            "download_result": self.download_result,
            "avg_block_query_time_ms": self.avg_block_query_time_ms,
        }


def _load_existing_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"invalid query log format in {path}: expected JSON array")
    return payload


def _duration_to_ms(value: float, unit: str) -> float:
    if unit == "s":
        return value * 1000.0
    if unit == "ms":
        return value
    if unit in {"us", "µs", "碌s", "纰宻"}:
        return value / 1000.0
    if unit == "ns":
        return value / 1_000_000.0
    raise ValueError(f"unsupported duration unit: {unit}")


def extract_avg_block_query_delays_ms(uread_stdout: str) -> list[float]:
    delays_ms: list[float] = []
    for match in _CLIENT_ACCESS_PATTERN.finditer(uread_stdout):
        raw_value = float(match.group(1))
        unit = match.group(2)
        delays_ms.append(_duration_to_ms(raw_value, unit))
    return delays_ms


def compute_avg_block_query_delay_ms(uread_stdout: str) -> float:
    delays_ms = extract_avg_block_query_delays_ms(uread_stdout)
    if not delays_ms:
        raise ValueError("no 'client access done in ...' entries found in uread output")
    return round(sum(delays_ms) / len(delays_ms), 4)


def write_query_log(
    query_username: str,
    db_name: str,
    file_name: str,
    download_action: str,
    download_result: str,
    avg_block_query_time_ms: float | None = None,
) -> dict[str, Any]:
    clean_username = query_username.strip() or "unknown"
    clean_db_name = db_name.strip()
    clean_file_name = file_name.strip()
    clean_action = download_action.strip()
    clean_result = download_result.strip()
    if not clean_db_name:
        raise ValueError("db_name is required")
    if not clean_file_name:
        raise ValueError("file_name is required")
    if not clean_action:
        raise ValueError("download_action is required")
    if not clean_result:
        raise ValueError("download_result is required")

    path = client_query_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = QueryLogEntry(
        query_username=clean_username,
        db_name=clean_db_name,
        file_name=clean_file_name,
        download_action=clean_action,
        query_time_utc=datetime.now(timezone.utc).isoformat(),
        download_result=clean_result,
        avg_block_query_time_ms=round(float(avg_block_query_time_ms), 4) if avg_block_query_time_ms is not None else None,
    )

    entries = _load_existing_entries(path)
    entries.append(entry.to_dict())
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "log_path": path,
        "entry": entry.to_dict(),
    }


def list_query_logs() -> list[dict[str, Any]]:
    path = client_query_log_path()
    entries = _load_existing_entries(path)
    return list(reversed(entries))
