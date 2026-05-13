from __future__ import annotations

from typing import Any, Callable

from client_ops.server_bridge import call_json
from database_registry import CLIENT_DB_PATH, get_entry, remove_prep_status, update_entry_prep_status


def prepare_client_preprocess(
    db_name: str,
    scheme: str,
    *,
    stop_local_jobs: Callable[[str], list[str]],
) -> dict[str, Any]:
    entry = get_entry(CLIENT_DB_PATH, db_name)
    if not entry:
        raise FileNotFoundError(f"database not found: {db_name}")

    current_status = str(entry.get("prep_status", "未完成"))
    stopped_local_jobs = stop_local_jobs(db_name)
    for stopped_scheme in stopped_local_jobs:
        current_status = remove_prep_status(current_status, stopped_scheme)

    current_status = remove_prep_status(current_status, scheme)
    client_entry = update_entry_prep_status(CLIENT_DB_PATH, db_name, current_status)

    server_result = call_json("POST", "/preprocess/prepare", {"db_name": db_name, "scheme": scheme})

    return {
        "db_name": db_name,
        "scheme": scheme,
        "stopped_local_jobs": stopped_local_jobs,
        "client_prep_status": client_entry["prep_status"],
        "server_result": server_result,
    }
