from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import client_preprocessing_log_path


@dataclass
class PreprocessingLogEntry:
    db_name: str
    scheme: str
    preprocessing_time_utc: str
    preprocessing_elapsed_ms: float
    preprocessing_result: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_name": self.db_name,
            "scheme": self.scheme,
            "preprocessing_time_utc": self.preprocessing_time_utc,
            "preprocessing_elapsed_ms": self.preprocessing_elapsed_ms,
            "preprocessing_result": self.preprocessing_result,
        }


def _load_existing_entries(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError(f"invalid preprocessing log format in {path}: expected JSON array")
    return payload


def write_preprocessing_log(
    db_name: str,
    scheme: str,
    preprocessing_elapsed_ms: float,
    preprocessing_result: str = "success",
) -> dict[str, Any]:
    path = client_preprocessing_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = PreprocessingLogEntry(
        db_name=db_name,
        scheme=scheme,
        preprocessing_time_utc=datetime.now(timezone.utc).isoformat(),
        preprocessing_elapsed_ms=round(preprocessing_elapsed_ms, 4),
        preprocessing_result=preprocessing_result,
    )

    entries = _load_existing_entries(path)
    entries.append(entry.to_dict())
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "log_path": path,
        "entry": entry.to_dict(),
    }
