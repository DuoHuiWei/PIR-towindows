from __future__ import annotations

from client_ops.client_delete_db import client_delete_db
from client_ops.server_bridge import server_manifest_exists
from client_ops.tmpdata_manager import clear_tmp_root
from config import manifest_path
from server_ops.new_folder_server import validate_db_name


def unfinished_clear(db_name: str) -> dict[str, object]:
    name = validate_db_name(db_name)

    client_manifest_exists = manifest_path(name).is_file()
    remote_manifest_exists = server_manifest_exists(name)

    if client_manifest_exists or remote_manifest_exists:
        raise ValueError(f"database already preprocessed: {name}")

    clear_tmp_root()
    delete_result = client_delete_db(name)
    return {
        "db_name": name,
        "tmpdata_cleared": True,
        "client_manifest_exists": client_manifest_exists,
        "server_manifest_exists": remote_manifest_exists,
        "delete_result": delete_result,
    }
