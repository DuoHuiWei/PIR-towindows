from __future__ import annotations

from pathlib import Path

from database_registry import CLIENT_DB_PATH, SERVER_DB_PATH, create_entry, get_entry
from client_ops.server_bridge import call_json
from config import client_data_item_dir, client_log_dir, client_manifest_dir
from server_ops.new_folder_server import validate_db_name


def list_client_databases() -> list[str]:
    entries = []
    try:
        from database_registry import list_entries

        entries = list_entries(CLIENT_DB_PATH)
    except Exception:
        return []
    return [entry["db_name"] for entry in entries]


def client_database_exists(db_name: str) -> bool:
    name = validate_db_name(db_name)
    return get_entry(CLIENT_DB_PATH, name) is not None


def ensure_client_base_dirs() -> list[Path]:
    created: list[Path] = []
    for path in (client_manifest_dir(), client_data_item_dir(), client_log_dir()):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
    return created


def new_folder_client(db_name: str) -> dict[str, object]:
    name = validate_db_name(db_name)

    if get_entry(CLIENT_DB_PATH, name) is not None:
        raise FileExistsError(f"database already exists: {name}")

    server_listing = call_json("GET", "/databases")
    existing_names = {item["db_name"] for item in server_listing.get("databases", [])}
    if name in existing_names:
        raise FileExistsError(f"database already exists: {name}")

    created_client_paths = [str(path) for path in ensure_client_base_dirs()]
    server_result = call_json("POST", "/databases/new-folder", {"db_name": name})
    client_entry = create_entry(CLIENT_DB_PATH, name)
    return {
        "db_name": name,
        "client_paths_ready": created_client_paths,
        "client_registry_entry": client_entry,
        "server_result": server_result,
    }
