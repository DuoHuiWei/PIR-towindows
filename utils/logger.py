from __future__ import annotations

from datetime import datetime
from pathlib import Path


LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "app.log"


def log_event(event: str, detail: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} [{event}] {detail}\n")
