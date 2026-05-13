from __future__ import annotations

import json
from pathlib import Path

from database_registry import SERVER_DB_PATH, list_entries, update_entry_stats
from config import server_data_root, snapshot_manifest_path, source_data_dir
from file_ops.pirexx_dataset_packer import pack_database
from server_ops.new_folder_server import validate_db_name


def list_databases() -> list[str]:
    return [entry["db_name"] for entry in list_entries(SERVER_DB_PATH)]


def ensure_database_exists(db_name: str) -> Path:
    db_name = validate_db_name(db_name)
    root = server_data_root() / db_name
    if not root.is_dir():
        raise FileNotFoundError(f"database not found: {db_name}")
    return root


def _manifest_files(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    files: list[dict[str, object]] = []
    for item in payload.get("files", []):
        files.append(
            {
                "file_id": item.get("file_id", item.get("file_name", "")),
                "file_name": item.get("file_name", item.get("file_id", "")),
                "size_bytes": int(item.get("size_bytes", 0)),
                "file_type": item.get("file_type", ""),
                "extension": item.get("extension", ""),
                "sha256": item.get("sha256", ""),
            }
        )
    return files


def list_manifest_files(db_name: str) -> list[dict[str, object]]:
    ensure_database_exists(db_name)
    return _manifest_files(snapshot_manifest_path(db_name))


def list_source_files(db_name: str) -> list[dict[str, object]]:
    # Kept only for upload/debug paths that need raw server source files.
    # User-facing database file listings must use list_manifest_files().
    ensure_database_exists(db_name)
    data_dir = source_data_dir(db_name)
    data_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, object]] = []
    for path in sorted(data_dir.iterdir()):
        if path.is_file():
            files.append(
                {
                    "file_name": path.name,
                    "size_bytes": path.stat().st_size,
                }
            )
    return files


def save_uploaded_files(db_name: str, files: list[tuple[str, bytes]], overwrite: bool = True) -> list[dict[str, object]]:
    ensure_database_exists(db_name)
    data_dir = source_data_dir(db_name)
    data_dir.mkdir(parents=True, exist_ok=True)

    saved: list[dict[str, object]] = []
    for file_name, content in files:
        target = data_dir / Path(file_name).name
        if target.exists() and not overwrite:
            raise FileExistsError(f"file already exists: {target.name}")
        target.write_bytes(content)
        saved.append(
            {
                "file_name": target.name,
                "size_bytes": len(content),
                "path": str(target),
            }
        )
    update_entry_stats(SERVER_DB_PATH, db_name, file_count_delta=len(saved), total_size_delta=sum(item["size_bytes"] for item in saved))
    return saved


def pack_database_snapshot(db_name: str, force: bool = True) -> dict[str, object]:
    ensure_database_exists(db_name)
    return pack_database(db_name, force=force)


def get_manifest_path(db_name: str) -> Path:
    ensure_database_exists(db_name)
    path = snapshot_manifest_path(db_name)
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found for database {db_name}: {path}")
    return path
