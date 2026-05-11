from __future__ import annotations

from database_registry import SERVER_DB_PATH, replace_entry_stats
from config import pirexx_dataset_capacity_bytes
from server_ops.database_manager import list_source_files, save_uploaded_files
from server_ops.new_folder_server import validate_db_name


def server_upload(db_name: str, files: list[tuple[str, bytes]]) -> dict[str, object]:
    name = validate_db_name(db_name)
    total_size = sum(len(content) for _, content in files)
    capacity = pirexx_dataset_capacity_bytes()
    if total_size > capacity:
        raise ValueError(f"upload total size exceeds dataset capacity: total={total_size}, limit={capacity}")

    saved = save_uploaded_files(name, files, overwrite=True)
    current_files = list_source_files(name)
    current_file_count = len(current_files)
    current_total_size_bytes = sum(int(item["size_bytes"]) for item in current_files)
    replace_entry_stats(
        SERVER_DB_PATH,
        name,
        file_count=current_file_count,
        total_size_bytes=current_total_size_bytes,
    )
    return {
        "db_name": name,
        "saved_files": saved,
        "saved_count": len(saved),
        "total_size_bytes": total_size,
        "capacity_bytes": capacity,
        "current_file_count": current_file_count,
        "current_total_size_bytes": current_total_size_bytes,
    }
