from __future__ import annotations

from database_registry import CLIENT_DB_PATH, delete_entry
from config import manifest_path
from client_ops.server_bridge import call_json
from server_ops.new_folder_server import validate_db_name


def client_delete_db(db_name: str) -> dict[str, object]:
    name = validate_db_name(db_name)
    server_result = call_json("DELETE", f"/databases/{name}")
    delete_entry(CLIENT_DB_PATH, name)

    local_manifest = manifest_path(name)
    manifest_deleted = False
    if local_manifest.exists():
        local_manifest.unlink()
        manifest_deleted = True

    return {
        "db_name": name,
        "server_result": server_result,
        "client_manifest_deleted": manifest_deleted,
        "client_manifest_path": str(local_manifest),
    }
