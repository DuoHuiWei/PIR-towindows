from __future__ import annotations

import re
from pathlib import Path

from database_registry import SERVER_DB_PATH, create_entry, get_entry
from config import database_root, source_data_dir, snapshot_dir


DB_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_db_name(db_name: str) -> str:
    normalized = db_name.strip()
    if not normalized:
        raise ValueError("db_name cannot be empty")
    if not DB_NAME_PATTERN.fullmatch(normalized):
        raise ValueError("db_name must match [A-Za-z0-9_-]+")
    return normalized


def server_database_exists(db_name: str) -> bool:
    name = validate_db_name(db_name)
    return get_entry(SERVER_DB_PATH, name) is not None


def new_folder_server(db_name: str) -> dict[str, object]:
    name = validate_db_name(db_name)
    root = database_root(name)
    if root.exists():
        raise FileExistsError(f"database already exists: {name}")

    created: list[Path] = []
    for path in (
        root,
        source_data_dir(name),
        snapshot_dir(name),
        root / "state-pirexx",
        root / "state-pirex",
    ):
        path.mkdir(parents=True, exist_ok=False)
        created.append(path)

    registry_entry = create_entry(SERVER_DB_PATH, name)

    return {
        "db_name": name,
        "root": root,
        "created_paths": [str(path) for path in created],
        "registry_entry": registry_entry,
    }


def register_database_on_server(db_name: str, *, created_at_utc: str | None = None) -> dict[str, object]:
    entry = create_entry(SERVER_DB_PATH, db_name, created_at_utc=created_at_utc)
    return entry
