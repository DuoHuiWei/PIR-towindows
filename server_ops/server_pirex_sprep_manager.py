from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any

from config import PIREX_SPREP_EXE, pirex_dataset_capacity_bytes, server_pirex_state_dir, snapshot_manifest_path
from database_registry import (
    SERVER_DB_PATH,
    get_entry,
    merge_prep_status,
    remove_prep_status,
    replace_entry_stats,
    update_entry_prep_status,
)
from server_ops.database_manager import list_source_files, pack_database_snapshot
from utils.rust_ctrl import find_free_tcp_port, spawn_process, stop_process, wait_for_tcp_listen


@dataclass
class PirexSprepState:
    db_name: str
    addr: str
    process: Any


def get_server_pirex_upload_status(db_name: str) -> dict[str, int | str]:
    files = list_source_files(db_name)
    total_size_bytes = sum(int(item["size_bytes"]) for item in files)
    replace_entry_stats(
        SERVER_DB_PATH,
        db_name,
        file_count=len(files),
        total_size_bytes=total_size_bytes,
    )
    return {
        "db_name": db_name,
        "file_count": len(files),
        "total_size_bytes": total_size_bytes,
        "capacity_bytes": pirex_dataset_capacity_bytes(),
    }


def ensure_pirex_sprep(current_state: PirexSprepState | None, db_name: str) -> tuple[PirexSprepState, dict[str, object]]:
    upload_status = get_server_pirex_upload_status(db_name)
    if int(upload_status["file_count"]) <= 0:
        raise ValueError("数据未上传")
    if int(upload_status["total_size_bytes"]) > int(upload_status["capacity_bytes"]):
        raise ValueError(
            f"database source size exceeds dataset capacity: total={upload_status['total_size_bytes']}, "
            f"limit={upload_status['capacity_bytes']}"
        )

    stop_pirex_sprep(current_state)
    clear_server_pirex_state(db_name)
    pack_result = pack_database_snapshot(db_name, force=True)

    if not PIREX_SPREP_EXE.is_file():
        raise FileNotFoundError(f"pirex_sprep executable not found: {PIREX_SPREP_EXE}")

    port = find_free_tcp_port()
    addr = f"127.0.0.1:{port}"
    process = spawn_process([str(PIREX_SPREP_EXE), db_name, addr])
    if not wait_for_tcp_listen(addr, process):
        stdout, stderr = process.communicate(timeout=1)
        raise RuntimeError(
            f"pirex_sprep failed to start for {db_name} at {addr}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    return PirexSprepState(db_name=db_name, addr=addr, process=process), pack_result


def delete_server_pirex_manifest(db_name: str) -> bool:
    path = snapshot_manifest_path(db_name)
    if not path.is_file():
        return False
    path.unlink()
    return True


def clear_server_pirex_state(db_name: str) -> None:
    state_dir = server_pirex_state_dir(db_name)
    if not state_dir.is_dir():
        return
    for child in state_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def finalize_pirex_sprep(
    current_state: PirexSprepState | None,
    db_name: str,
    *,
    preprocess_succeeded: bool,
) -> dict[str, object]:
    stopped = False
    if current_state is not None:
        stop_pirex_sprep(current_state)
        stopped = True

    current_entry = get_entry(SERVER_DB_PATH, db_name)
    current_status = current_entry["prep_status"] if current_entry else "未完成"

    manifest_deleted = False
    if preprocess_succeeded:
        prep_status = merge_prep_status(current_status, "pirex")
    else:
        clear_server_pirex_state(db_name)
        prep_status = remove_prep_status(current_status, "pirex")
        if prep_status == "未完成":
            manifest_deleted = delete_server_pirex_manifest(db_name)

    update_entry_prep_status(SERVER_DB_PATH, db_name, prep_status)
    return {
        "db_name": db_name,
        "stopped": stopped,
        "server_manifest_deleted": manifest_deleted,
        "prep_status": prep_status,
    }


def stop_pirex_sprep(state: PirexSprepState | None) -> None:
    if state is None:
        return
    stop_process(state.process)
