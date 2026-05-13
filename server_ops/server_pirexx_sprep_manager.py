from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import PIREXX_SPREP_EXE, WORKSPACE_ROOT, pirexx_dataset_capacity_bytes, server_pirexx_state_dir, snapshot_manifest_path
from database_registry import (
    SERVER_DB_PATH,
    get_entry,
    merge_prep_status,
    remove_prep_status,
    replace_entry_stats,
    update_entry_prep_status,
)
from server_ops.database_manager import list_source_files, pack_database_snapshot
from utils.rust_ctrl import find_free_tcp_port, read_process_log, spawn_logged_process, stop_process, wait_for_tcp_listen


@dataclass
class PirexxSprepState:
    db_name: str
    addr: str
    process: Any
    log_path: Path


def _pirexx_sprep_log_path(db_name: str) -> Path:
    return WORKSPACE_ROOT / "logs" / "rust-subprocess" / f"pirexx_sprep_{db_name}.log"


def get_server_upload_status(db_name: str) -> dict[str, int | str]:
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
        "capacity_bytes": pirexx_dataset_capacity_bytes(),
    }


def ensure_pirexx_sprep(current_state: PirexxSprepState | None, db_name: str) -> tuple[PirexxSprepState, dict[str, object]]:
    upload_status = get_server_upload_status(db_name)
    if int(upload_status["file_count"]) <= 0:
        raise ValueError("数据未上传")
    if int(upload_status["total_size_bytes"]) > int(upload_status["capacity_bytes"]):
        raise ValueError(
            f"database source size exceeds dataset capacity: total={upload_status['total_size_bytes']}, "
            f"limit={upload_status['capacity_bytes']}"
        )

    stop_pirexx_sprep(current_state)
    clear_server_pirexx_state(db_name)
    pack_result = pack_database_snapshot(db_name, force=True)

    if not PIREXX_SPREP_EXE.is_file():
        raise FileNotFoundError(f"pirexx_sprep executable not found: {PIREXX_SPREP_EXE}")

    port = find_free_tcp_port()
    addr = f"127.0.0.1:{port}"
    log_path = _pirexx_sprep_log_path(db_name)
    process = spawn_logged_process([str(PIREXX_SPREP_EXE), db_name, addr], log_path)
    if not wait_for_tcp_listen(addr, process):
        output = read_process_log(log_path)
        raise RuntimeError(
            f"pirexx_sprep failed to start for {db_name} at {addr}\nlog_path: {log_path}\noutput:\n{output}"
        )

    return PirexxSprepState(db_name=db_name, addr=addr, process=process, log_path=log_path), pack_result


def delete_server_manifest(db_name: str) -> bool:
    path = snapshot_manifest_path(db_name)
    if not path.is_file():
        return False
    path.unlink()
    return True


def clear_server_pirexx_state(db_name: str) -> None:
    state_dir = server_pirexx_state_dir(db_name)
    if not state_dir.is_dir():
        return
    for child in state_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def finalize_pirexx_sprep(
    current_state: PirexxSprepState | None,
    db_name: str,
    *,
    preprocess_succeeded: bool,
) -> dict[str, object]:
    stopped = False
    if current_state is not None:
        stop_pirexx_sprep(current_state)
        stopped = True

    current_entry = get_entry(SERVER_DB_PATH, db_name)
    current_status = current_entry["prep_status"] if current_entry else "未完成"

    manifest_deleted = False
    if preprocess_succeeded:
        prep_status = merge_prep_status(current_status, "pirexx")
    else:
        clear_server_pirexx_state(db_name)
        prep_status = remove_prep_status(current_status, "pirexx")
        if prep_status == "未完成":
            manifest_deleted = delete_server_manifest(db_name)

    update_entry_prep_status(SERVER_DB_PATH, db_name, prep_status)
    return {
        "db_name": db_name,
        "stopped": stopped,
        "server_manifest_deleted": manifest_deleted,
        "prep_status": prep_status,
    }


def stop_pirexx_sprep(state: PirexxSprepState | None) -> None:
    if state is None:
        return
    stop_process(state.process)
