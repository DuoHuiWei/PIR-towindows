from __future__ import annotations

import json

from config import manifest_path
from server_ops.new_folder_server import validate_db_name


def list_client_manifest_files(db_name: str) -> list[dict[str, object]]:
    name = validate_db_name(db_name)
    path = manifest_path(name)
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
