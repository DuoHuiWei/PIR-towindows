from __future__ import annotations

import shutil

from database_registry import SERVER_DB_PATH, delete_entry, get_entry
from config import database_root
from server_ops.new_folder_server import validate_db_name


def server_delete_db(db_name: str) -> dict[str, object]:
    name = validate_db_name(db_name)
    root = database_root(name)
    registry_exists = get_entry(SERVER_DB_PATH, name) is not None
    root_exists = root.is_dir()

    if not root_exists and not registry_exists:
        return {
            "db_name": name,
            "deleted_root": str(root),
            "root_deleted": False,
            "registry_deleted": False,
            "already_absent": True,
        }

    if root_exists:
        shutil.rmtree(root)

    registry_deleted = False
    if registry_exists:
        delete_entry(SERVER_DB_PATH, name)
        registry_deleted = True

    return {
        "db_name": name,
        "deleted_root": str(root),
        "root_deleted": root_exists,
        "registry_deleted": registry_deleted,
        "already_absent": False,
    }
