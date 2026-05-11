from __future__ import annotations

import hashlib
from pathlib import Path

from config import client_tmpdata_root, pirexx_dataset_capacity_bytes
from server_ops.new_folder_server import validate_db_name


def dataset_capacity_bytes() -> int:
    return pirexx_dataset_capacity_bytes()


def ensure_tmp_root() -> Path:
    root = client_tmpdata_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_tmp_files() -> list[dict[str, object]]:
    root = client_tmpdata_root()
    if not root.exists():
        return []

    files: list[dict[str, object]] = []
    for path in sorted(root.iterdir()):
        if path.is_file():
            files.append(
                {
                    "file_name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "path": str(path),
                }
            )
    return files


def tmp_total_size() -> int:
    return sum(int(item["size_bytes"]) for item in list_tmp_files())


def save_tmp_files(db_name: str, files: list[tuple[str, bytes]]) -> dict[str, object]:
    validate_db_name(db_name)
    root = ensure_tmp_root()

    existing_names = {item["file_name"] for item in list_tmp_files()}
    filtered_files = [(file_name, content) for file_name, content in files if Path(file_name).name not in existing_names]

    existing_size = tmp_total_size()
    incoming_size = sum(len(content) for _, content in filtered_files)
    capacity = dataset_capacity_bytes()
    if existing_size + incoming_size > capacity:
        raise ValueError(
            f"tmpdata capacity exceeded: current={existing_size}, incoming={incoming_size}, limit={capacity}"
        )

    saved: list[dict[str, object]] = []
    skipped: list[str] = []
    for file_name, content in files:
        normalized_name = Path(file_name).name
        if normalized_name in existing_names:
            skipped.append(normalized_name)
            continue

        target = root / normalized_name
        target.write_bytes(content)
        saved.append(
            {
                "file_name": target.name,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "path": str(target),
            }
        )

    return {
        "db_name": db_name,
        "saved_files": saved,
        "skipped_files": skipped,
        "tmp_total_size": tmp_total_size(),
        "capacity_bytes": capacity,
    }


def load_tmp_files_for_upload(db_name: str) -> list[tuple[str, bytes, str]]:
    validate_db_name(db_name)
    payloads: list[tuple[str, bytes, str]] = []
    for item in list_tmp_files():
        path = Path(str(item["path"]))
        payloads.append((str(item["file_name"]), path.read_bytes(), "application/octet-stream"))
    return payloads


def remove_tmp_file(file_name: str) -> None:
    target = client_tmpdata_root() / Path(file_name).name
    if not target.exists():
        raise FileNotFoundError(f"tmpdata file not found: {target.name}")
    target.unlink()


def clear_tmp_root() -> None:
    root = client_tmpdata_root()
    if not root.exists():
        return

    for path in root.iterdir():
        if path.is_file():
            path.unlink()
