from __future__ import annotations

import threading
import time

from client_ops.preprocessing_log import write_preprocessing_log
from client_ops.server_bridge import call_json, download_manifest_to_client
from config import PIREXX_UPREP_EXE, pirexx_dataset_capacity_bytes
from database_registry import CLIENT_DB_PATH, get_entry, merge_prep_status, remove_prep_status, replace_entry_stats, update_entry_prep_status
from utils.rust_ctrl import spawn_process, stop_process


def _print_subprocess_output(prefix: str, stdout: str, stderr: str) -> None:
    stdout_text = stdout.strip()
    stderr_text = stderr.strip()

    if stdout_text:
        print(f"{prefix} stdout begin")
        print(stdout_text)
        print(f"{prefix} stdout end")

    if stderr_text:
        print(f"{prefix} stderr begin")
        print(stderr_text)
        print(f"{prefix} stderr end")


def _wait_abortable(process, cancel_event: threading.Event, poll_interval_s: float = 0.2) -> tuple[int, str, str]:
    while process.poll() is None:
        if cancel_event.is_set():
            stop_process(process)
            stdout, stderr = process.communicate(timeout=1)
            raise RuntimeError(f"preprocessing cancelled by user\nstdout:\n{stdout}\nstderr:\n{stderr}")
        time.sleep(poll_interval_s)
    stdout, stderr = process.communicate(timeout=1)
    return int(process.returncode or 0), stdout, stderr


def run_client_pirexx_uprep(db_name: str, cancel_event: threading.Event | None = None) -> dict[str, object]:
    task_cancel_event = cancel_event or threading.Event()
    upload_status = call_json("GET", f"/databases/{db_name}/upload-status")
    file_count = int(upload_status.get("file_count", 0))
    total_size_bytes = int(upload_status.get("total_size_bytes", 0))
    capacity_bytes = int(upload_status.get("capacity_bytes", pirexx_dataset_capacity_bytes()))

    if file_count <= 0:
        raise ValueError("数据未上传")
    if total_size_bytes > capacity_bytes:
        raise ValueError(f"database source size exceeds dataset capacity: total={total_size_bytes}, limit={capacity_bytes}")

    replace_entry_stats(
        CLIENT_DB_PATH,
        db_name,
        file_count=file_count,
        total_size_bytes=total_size_bytes,
    )

    current_entry = get_entry(CLIENT_DB_PATH, db_name)
    previous_status = current_entry["prep_status"] if current_entry else "未完成"

    start_payload = call_json("POST", "/pirexx/preprocess/start", {"db_name": db_name})
    server_addr = str(start_payload.get("server_addr", ""))
    if not server_addr:
        raise RuntimeError(f"invalid preprocess start response: {start_payload}")

    if not PIREXX_UPREP_EXE.is_file():
        raise FileNotFoundError(f"pirexx_uprep executable not found: {PIREXX_UPREP_EXE}")

    start = time.perf_counter()
    finalized = False
    try:
        process = spawn_process([str(PIREXX_UPREP_EXE), db_name, server_addr])
        return_code, stdout, stderr = _wait_abortable(process, task_cancel_event)
        _print_subprocess_output(f"pirexx_uprep[{db_name}]", stdout, stderr)
        if return_code != 0:
            raise RuntimeError(f"pirexx_uprep failed for {db_name}\nstdout:\n{stdout}\nstderr:\n{stderr}")
        if "uprep: completed successfully" not in stdout:
            raise RuntimeError(f"pirexx_uprep did not report success for {db_name}\nstdout:\n{stdout}\nstderr:\n{stderr}")

        manifest_local_path = download_manifest_to_client(db_name)
        finalize_payload = call_json("POST", "/pirexx/preprocess/finalize", {"db_name": db_name, "success": True})
        finalized = True

        update_entry_prep_status(CLIENT_DB_PATH, db_name, merge_prep_status(previous_status, "pirexx"))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        log_result = write_preprocessing_log(
            db_name=db_name,
            scheme="pirexx",
            preprocessing_elapsed_ms=elapsed_ms,
            preprocessing_result="success",
        )

        return {
            "db_name": db_name,
            "server_addr": server_addr,
            "manifest_local_path": str(manifest_local_path),
            "server_finalize_result": finalize_payload,
            "preprocessing_log": log_result,
            "uprep_stdout": stdout,
            "uprep_stderr": stderr,
            "preprocessing_elapsed_ms": log_result["entry"]["preprocessing_elapsed_ms"],
        }
    except Exception:
        if not finalized:
            try:
                call_json("POST", "/pirexx/preprocess/finalize", {"db_name": db_name, "success": False})
            except Exception:
                pass
        update_entry_prep_status(CLIENT_DB_PATH, db_name, remove_prep_status(previous_status, "pirexx"))
        raise
