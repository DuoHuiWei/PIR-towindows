from __future__ import annotations

import shutil

from database_registry import SERVER_DB_PATH, delete_entry
from config import database_root
from server_ops.new_folder_server import validate_db_name


def server_delete_db(db_name: str) -> dict[str, object]:
    name = validate_db_name(db_name)
    root = database_root(name)
    if not root.is_dir():
        raise FileNotFoundError(f"database not found: {name}")

    shutil.rmtree(root)
    delete_entry(SERVER_DB_PATH, name)
    return {
        "db_name": name,
        "deleted_root": str(root),
    }
