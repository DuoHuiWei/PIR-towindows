from __future__ import annotations

from database_registry import CLIENT_DB_PATH, delete_entry, get_entry
from config import manifest_path
from client_ops.server_bridge import call_json
from server_ops.new_folder_server import validate_db_name


def client_delete_db(db_name: str) -> dict[str, object]:
    name = validate_db_name(db_name)
    try:
        server_result = call_json("DELETE", f"/databases/{name}")
    except RuntimeError as exc:
        detail = str(exc)
        if "HTTP 400" in detail and f'database not found: {name}' in detail:
            server_result = {
                "ok": True,
                "db_name": name,
                "already_absent": True,
                "detail": "server database already absent",
            }
        else:
            raise

    local_registry_deleted = False
    if get_entry(CLIENT_DB_PATH, name) is not None:
        delete_entry(CLIENT_DB_PATH, name)
        local_registry_deleted = True

    local_manifest = manifest_path(name)
    manifest_deleted = False
    if local_manifest.exists():
        local_manifest.unlink()
        manifest_deleted = True

    return {
        "db_name": name,
        "server_result": server_result,
        "client_registry_deleted": local_registry_deleted,
        "client_manifest_deleted": manifest_deleted,
        "client_manifest_path": str(local_manifest),
    }
