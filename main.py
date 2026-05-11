from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from urllib import error, request
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth.auth import LoginRequest, authenticate_user
from client_ops.client_account_manager import add_user, delete_user, list_users, reset_password
from client_ops.client_delete_db import client_delete_db
from client_ops.client_manifest_files import list_client_manifest_files
from client_ops.client_pirex_uprep_manager import run_client_pirex_uprep
from client_ops.client_pirexx_uprep_manager import run_client_pirexx_uprep
from client_ops.new_folder_client import new_folder_client
from client_ops.all_log import write_all_log
from client_ops.qurey_log import compute_avg_block_query_delay_ms, list_query_logs, write_query_log
from client_ops.server_bridge import call_json, download_manifest_to_client, upload_files
from client_ops.tmpdata_manager import (
    clear_tmp_root,
    list_tmp_files,
    load_tmp_files_for_upload,
    remove_tmp_file,
    save_tmp_files,
)
from client_ops.unfinished_clear import unfinished_clear
from client_ops.database_log import list_database_logs, write_database_log
from client_ops.preprocessing_log import write_preprocessing_log
from client_ops.user_manager_log import list_user_manager_logs, write_user_manager_log
from config import SERVER_API_BASE_URL, SHOW_UPLOAD_LIMIT_HINT, pirexx_dataset_capacity_bytes
from database_registry import (
    CLIENT_DB_PATH,
    SERVER_DB_PATH,
    get_entry,
    list_entries,
    replace_entry_stats,
)
from file_ops.direct_restore import direct_restore
from file_ops.pirex_dataset_restore import restore_pirex_file
from file_ops.pirexx_dataset_restore import restore_pirexx_file
from server_ops.database_manager import (
    get_manifest_path,
    list_databases,
    list_manifest_files,
    list_source_files,
    pack_database_snapshot,
)
from server_ops.pirex_sread_manager import (
    PirexSreadState,
    ensure_pirex_sread,
    stop_pirex_sread,
)
from server_ops.server_delete_db import server_delete_db
from server_ops.new_folder_server import new_folder_server
from server_ops.server_pirex_sprep_manager import (
    PirexSprepState,
    ensure_pirex_sprep,
    finalize_pirex_sprep,
)
from server_ops.server_pirexx_sprep_manager import (
    PirexxSprepState,
    ensure_pirexx_sprep,
    finalize_pirexx_sprep,
)
from server_ops.server_upload import server_upload
from server_ops.pirexx_sread_manager import PirexxSreadState, ensure_pirexx_sread, stop_pirexx_sread
from utils.logger import log_event


def build_app(title: str) -> FastAPI:
    app = FastAPI(title=title)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


client_app = build_app("PIREXX Client API")
server_app = build_app("PIREXX Server API")
client_app.mount("/static", StaticFiles(directory="static"), name="static")
INDEX_HTML_PATH = Path("templates") / "index.html"


class RestoreRequest(BaseModel):
    db_name: str
    file_id: str
    force: bool = False
    query_user: str = ""
    download_dir: str = ""


class DatabaseCreateRequest(BaseModel):
    db_name: str


class ServerStartRequest(BaseModel):
    db_name: str


class PreprocessFinalizeRequest(BaseModel):
    db_name: str
    success: bool


class PreprocessJobRequest(BaseModel):
    db_name: str
    scheme: str


class TmpDeleteRequest(BaseModel):
    file_name: str


class AccountDeleteRequest(BaseModel):
    username: str
    admin_username: str = ""


class AccountResetRequest(BaseModel):
    username: str
    new_password: str
    admin_username: str = ""


class AccountAddRequest(BaseModel):
    nickname: str
    username: str
    password: str
    admin_username: str = ""


_sread_lock = threading.Lock()
_pirexx_sread_state: PirexxSreadState | None = None
_pirexx_sprep_lock = threading.Lock()
_pirexx_sprep_state: PirexxSprepState | None = None
_pirex_sprep_lock = threading.Lock()
_pirex_sprep_state: PirexSprepState | None = None
_pirex_sread_lock = threading.Lock()
_pirex_sread_state: PirexSreadState | None = None
_selected_db_lock = threading.Lock()
_selected_pirexx_db_name = ""
_selected_pirexx_server_addr = ""
_selected_pirex_db_lock = threading.Lock()
_selected_pirex_db_name = ""
_selected_pirex_server_addr = ""
_preprocess_job_lock = threading.Lock()
_preprocess_jobs: dict[str, dict[str, Any]] = {}


def ensure_server_pirexx_sread(db_name: str) -> str:
    global _pirexx_sread_state

    with _sread_lock:
        _pirexx_sread_state = ensure_pirexx_sread(_pirexx_sread_state, db_name)
        return _pirexx_sread_state.addr


def ensure_server_pirex_sread(db_name: str) -> str:
    global _pirex_sread_state

    with _pirex_sread_lock:
        _pirex_sread_state = ensure_pirex_sread(_pirex_sread_state, db_name)
        return _pirex_sread_state.addr


def request_server_pirexx_sread(db_name: str) -> str:
    payload = json.dumps({"db_name": db_name}).encode("utf-8")
    http_request = request.Request(
        url=f"{SERVER_API_BASE_URL}/pirexx/sread/start_or_switch",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"server API returned HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"server API not reachable: {exc}") from exc

    if "server_addr" not in body:
        raise RuntimeError(f"invalid server API response: {body}")
    return str(body["server_addr"])


def request_server_pirex_sread(db_name: str) -> str:
    payload = json.dumps({"db_name": db_name}).encode("utf-8")
    http_request = request.Request(
        url=f"{SERVER_API_BASE_URL}/pirex/sread/start_or_switch",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"server API returned HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"server API not reachable: {exc}") from exc

    if "server_addr" not in body:
        raise RuntimeError(f"invalid server API response: {body}")
    return str(body["server_addr"])


def set_selected_pirexx_database(db_name: str, server_addr: str) -> None:
    global _selected_pirexx_db_name, _selected_pirexx_server_addr
    with _selected_db_lock:
        _selected_pirexx_db_name = db_name
        _selected_pirexx_server_addr = server_addr


def get_selected_pirexx_database() -> tuple[str, str]:
    with _selected_db_lock:
        return _selected_pirexx_db_name, _selected_pirexx_server_addr


def set_selected_pirex_database(db_name: str, server_addr: str) -> None:
    global _selected_pirex_db_name, _selected_pirex_server_addr
    with _selected_pirex_db_lock:
        _selected_pirex_db_name = db_name
        _selected_pirex_server_addr = server_addr


def get_selected_pirex_database() -> tuple[str, str]:
    with _selected_pirex_db_lock:
        return _selected_pirex_db_name, _selected_pirex_server_addr


def _normalize_preprocess_scheme(scheme: str) -> str:
    normalized = scheme.strip().lower()
    if normalized not in {"pirex", "pirexx"}:
        raise ValueError(f"unsupported preprocess scheme: {scheme}")
    return normalized


def _serialize_preprocess_job(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {
            "active": False,
            "status": "idle",
        }

    started_at = float(job.get("started_at", time.time()))
    ended_at = job.get("ended_at")
    now = time.time()
    elapsed_ms = ((ended_at if isinstance(ended_at, (int, float)) else now) - started_at) * 1000.0
    return {
        "active": bool(job.get("status") == "running"),
        "status": str(job.get("status", "idle")),
        "scheme": str(job.get("scheme", "")),
        "db_name": str(job.get("db_name", "")),
        "error": str(job.get("error", "")),
        "started_at": started_at,
        "ended_at": ended_at,
        "elapsed_ms": round(elapsed_ms, 4),
        "cancel_requested": bool(job.get("cancel_requested", False)),
    }


def _write_preprocess_failure_updates(db_name: str, scheme: str, status: str, elapsed_ms: float) -> None:
    result_label = "cancelled" if status == "cancelled" else "failed"
    write_preprocessing_log(
        db_name=db_name,
        scheme=scheme,
        preprocessing_elapsed_ms=elapsed_ms,
        preprocessing_result=result_label,
    )
    write_database_log(db_name, f"预处理({scheme})", "中止" if status == "cancelled" else "失败")


def _run_preprocess_job(scheme: str, db_name: str, cancel_event: threading.Event) -> None:
    started_at = time.time()
    try:
        if scheme == "pirex":
            result = run_client_pirex_uprep(db_name, cancel_event)
        else:
            result = run_client_pirexx_uprep(db_name, cancel_event)

        with _preprocess_job_lock:
            job = _preprocess_jobs.get(scheme, {})
            job.update(
                {
                    "status": "completed",
                    "ended_at": time.time(),
                    "result": result,
                    "error": "",
                    "cancel_requested": False,
                }
            )
            _preprocess_jobs[scheme] = job

        write_database_log(db_name, f"预处理({scheme})", "成功")
    except Exception as exc:
        ended_at = time.time()
        elapsed_ms = (ended_at - started_at) * 1000.0
        status = "cancelled" if cancel_event.is_set() else "failed"
        _write_preprocess_failure_updates(db_name, scheme, status, elapsed_ms)
        with _preprocess_job_lock:
            job = _preprocess_jobs.get(scheme, {})
            job.update(
                {
                    "status": status,
                    "ended_at": ended_at,
                    "result": None,
                    "error": str(exc),
                    "cancel_requested": False,
                }
            )
            _preprocess_jobs[scheme] = job


def _start_preprocess_job(db_name: str, scheme: str) -> dict[str, Any]:
    normalized_scheme = _normalize_preprocess_scheme(scheme)
    with _preprocess_job_lock:
        existing = _preprocess_jobs.get(normalized_scheme)
        if existing and existing.get("status") == "running":
            raise RuntimeError(f"{normalized_scheme} preprocess is already running")

        cancel_event = threading.Event()
        job = {
            "scheme": normalized_scheme,
            "db_name": db_name,
            "status": "running",
            "started_at": time.time(),
            "ended_at": None,
            "error": "",
            "result": None,
            "cancel_requested": False,
            "cancel_event": cancel_event,
        }
        thread = threading.Thread(
            target=_run_preprocess_job,
            args=(normalized_scheme, db_name, cancel_event),
            daemon=True,
        )
        job["thread"] = thread
        _preprocess_jobs[normalized_scheme] = job
        thread.start()
        return _serialize_preprocess_job(job)


def _cancel_preprocess_job(db_name: str, scheme: str) -> dict[str, Any]:
    normalized_scheme = _normalize_preprocess_scheme(scheme)
    with _preprocess_job_lock:
        job = _preprocess_jobs.get(normalized_scheme)
        if not job or job.get("status") != "running":
            raise RuntimeError(f"no running {normalized_scheme} preprocess job")
        if job.get("db_name") != db_name:
            raise RuntimeError(f"running {normalized_scheme} preprocess job belongs to {job.get('db_name')}")
        cancel_event = job["cancel_event"]
        cancel_event.set()
        job["cancel_requested"] = True
        return _serialize_preprocess_job(job)


def _stop_client_preprocess_jobs_for_db(db_name: str, join_timeout_s: float = 5.0) -> list[str]:
    stopped_schemes: list[str] = []
    threads_to_join: list[threading.Thread] = []

    with _preprocess_job_lock:
        for scheme, job in _preprocess_jobs.items():
            if job.get("status") != "running":
                continue
            if job.get("db_name") != db_name:
                continue
            cancel_event = job.get("cancel_event")
            if cancel_event is not None:
                cancel_event.set()
            job["cancel_requested"] = True
            stopped_schemes.append(scheme)
            thread = job.get("thread")
            if isinstance(thread, threading.Thread):
                threads_to_join.append(thread)

    for thread in threads_to_join:
        thread.join(timeout=join_timeout_s)

    return stopped_schemes


def _stop_server_processes_for_db(db_name: str) -> dict[str, bool]:
    global _pirexx_sread_state, _pirex_sread_state, _pirexx_sprep_state, _pirex_sprep_state

    stopped = {
        "pirexx_sread": False,
        "pirex_sread": False,
        "pirexx_sprep": False,
        "pirex_sprep": False,
    }

    with _sread_lock:
        if _pirexx_sread_state is not None and _pirexx_sread_state.db_name == db_name:
            stop_pirexx_sread(_pirexx_sread_state)
            _pirexx_sread_state = None
            stopped["pirexx_sread"] = True

    with _pirex_sread_lock:
        if _pirex_sread_state is not None and _pirex_sread_state.db_name == db_name:
            stop_pirex_sread(_pirex_sread_state)
            _pirex_sread_state = None
            stopped["pirex_sread"] = True

    with _pirexx_sprep_lock:
        if _pirexx_sprep_state is not None and _pirexx_sprep_state.db_name == db_name:
            finalize_pirexx_sprep(_pirexx_sprep_state, db_name, preprocess_succeeded=False)
            _pirexx_sprep_state = None
            stopped["pirexx_sprep"] = True

    with _pirex_sprep_lock:
        if _pirex_sprep_state is not None and _pirex_sprep_state.db_name == db_name:
            finalize_pirex_sprep(_pirex_sprep_state, db_name, preprocess_succeeded=False)
            _pirex_sprep_state = None
            stopped["pirex_sprep"] = True

    with _selected_db_lock:
        global _selected_pirexx_db_name, _selected_pirexx_server_addr
        if _selected_pirexx_db_name == db_name:
            _selected_pirexx_db_name = ""
            _selected_pirexx_server_addr = ""

    with _selected_pirex_db_lock:
        global _selected_pirex_db_name, _selected_pirex_server_addr
        if _selected_pirex_db_name == db_name:
            _selected_pirex_db_name = ""
            _selected_pirex_server_addr = ""

    return stopped


@client_app.get("/health")
def client_health() -> dict[str, str]:
    return {"status": "ok", "role": "client"}


@client_app.get("/config/upload-limits")
def client_upload_limits() -> dict[str, Any]:
    return {
        "ok": True,
        "dataset_capacity_bytes": pirexx_dataset_capacity_bytes(),
        "show_upload_limit_hint": SHOW_UPLOAD_LIMIT_HINT,
    }


@client_app.get("/")
def client_index() -> FileResponse:
    return FileResponse(INDEX_HTML_PATH)


@client_app.get("/recover-file/{file_name}")
def client_download_recovered_file(file_name: str) -> FileResponse:
    from config import recover_root

    target = recover_root() / file_name
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"recovered file not found: {file_name}")
    return FileResponse(target, filename=file_name)


@server_app.get("/health")
def server_health() -> dict[str, str]:
    return {"status": "ok", "role": "server"}


@server_app.get("/databases")
def server_list_databases() -> dict[str, Any]:
    items = []
    for entry in list_entries(SERVER_DB_PATH):
        db_name = entry["db_name"]
        items.append(
            {
                "db_name": db_name,
                "files": [],
                "created_at_utc": entry["created_at_utc"],
                "file_count": entry["file_count"],
                "total_size_bytes": entry["total_size_bytes"],
                "prep_status": entry["prep_status"],
            }
        )
    return {"ok": True, "databases": items}


@server_app.post("/databases/new-folder")
def server_create_database(payload: DatabaseCreateRequest) -> dict[str, Any]:
    try:
        result = new_folder_server(payload.db_name)
    except Exception as exc:
        log_event("database_create_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("database_create", f"db={payload.db_name}")
    return {
        "ok": True,
        "db_name": result["db_name"],
        "created_paths": result["created_paths"],
    }


@server_app.get("/databases/{db_name}/files")
def server_list_database_files(db_name: str) -> dict[str, Any]:
    try:
        files = list_manifest_files(db_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "db_name": db_name, "files": files}


@server_app.get("/databases/{db_name}/upload-status")
def server_database_upload_status(db_name: str) -> dict[str, Any]:
    try:
        files = list_source_files(db_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    total_size_bytes = sum(int(item["size_bytes"]) for item in files)
    return {
        "ok": True,
        "db_name": db_name,
        "file_count": len(files),
        "total_size_bytes": total_size_bytes,
        "capacity_bytes": pirexx_dataset_capacity_bytes(),
    }


@server_app.delete("/databases/{db_name}")
def server_delete_database(db_name: str) -> dict[str, Any]:
    try:
        stopped = _stop_server_processes_for_db(db_name)
        result = server_delete_db(db_name)
    except Exception as exc:
        log_event("database_delete_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("database_delete", f"db={db_name} stopped={stopped}")
    return {"ok": True, **result, "stopped_processes": stopped}


@server_app.post("/databases/{db_name}/upload")
async def server_upload_files(db_name: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:
    try:
        payloads: list[tuple[str, bytes]] = []
        for upload in files:
            payloads.append((upload.filename or "unnamed.bin", await upload.read()))
        result = server_upload(db_name, payloads)
    except Exception as exc:
        log_event("database_upload_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("database_upload", f"db={db_name} files={result['saved_count']}")
    return {"ok": True, **result}


@server_app.post("/databases/{db_name}/pack")
def server_pack_database(db_name: str, force: bool = Query(True)) -> dict[str, Any]:
    try:
        result = pack_database_snapshot(db_name, force=force)
    except Exception as exc:
        log_event("database_pack_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("database_pack", f"db={db_name} files={result['files_packed']} blocks={result['used_blocks']}")
    return {
        "ok": True,
        "db_name": result["db_name"],
        "packed_data_path": str(result["packed_data_path"]),
        "manifest_path": str(result["manifest_path"]),
        "files_packed": result["files_packed"],
        "used_blocks": result["used_blocks"],
        "unused_blocks": result["unused_blocks"],
    }


@server_app.get("/databases/{db_name}/manifest")
def server_download_manifest(db_name: str) -> FileResponse:
    try:
        path = get_manifest_path(db_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/json", filename=path.name)


@client_app.post("/auth/login")
def client_login(payload: LoginRequest) -> dict[str, Any]:
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid username or password")

    log_event("login", f"user={user['username']} role={user['role']}")
    return {
        "ok": True,
        "user": {
            "username": user["username"],
            "nickname": user["nickname"],
            "role": user["role"],
        },
    }


@client_app.get("/accounts")
def client_list_accounts(keyword: str = Query("")) -> dict[str, Any]:
    try:
        users = list_users(keyword)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "users": users}


@client_app.get("/logs/database")
def client_database_logs(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    try:
        entries = list_database_logs()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    total = len(entries)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    start = (current_page - 1) * page_size
    end = start + page_size

    return {
        "ok": True,
        "items": entries[start:end],
        "page": current_page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


@client_app.get("/logs/query")
def client_query_logs(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    try:
        entries = list_query_logs()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    total = len(entries)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    start = (current_page - 1) * page_size
    end = start + page_size

    return {
        "ok": True,
        "items": entries[start:end],
        "page": current_page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


@client_app.get("/logs/user-manager")
def client_user_manager_logs(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    try:
        entries = list_user_manager_logs()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    total = len(entries)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    start = (current_page - 1) * page_size
    end = start + page_size

    return {
        "ok": True,
        "items": entries[start:end],
        "page": current_page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


@client_app.post("/accounts/delete")
def client_delete_account(payload: AccountDeleteRequest) -> dict[str, Any]:
    try:
        result = delete_user(payload.username)
        write_user_manager_log(
            admin_username=payload.admin_username,
            admin_action="删除",
            target_username=str(result["username"]),
            target_nickname=str(result["nickname"]),
        )
    except Exception as exc:
        log_event("client_account_delete_error", f"user={payload.username} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_account_delete", f"user={payload.username}")
    return {"ok": True, **result}


@client_app.post("/accounts/reset-password")
def client_reset_account_password(payload: AccountResetRequest) -> dict[str, Any]:
    try:
        result = reset_password(payload.username, payload.new_password)
        write_user_manager_log(
            admin_username=payload.admin_username,
            admin_action="重置",
            target_username=str(result["username"]),
            target_nickname=str(result["nickname"]),
        )
    except Exception as exc:
        log_event("client_account_reset_error", f"user={payload.username} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_account_reset", f"user={payload.username}")
    return {"ok": True, **result}


@client_app.post("/accounts/add")
def client_add_account(payload: AccountAddRequest) -> dict[str, Any]:
    try:
        user = add_user(payload.nickname, payload.username, payload.password)
        write_user_manager_log(
            admin_username=payload.admin_username,
            admin_action="添加",
            target_username=str(user["username"]),
            target_nickname=str(user["nickname"]),
        )
    except Exception as exc:
        log_event("client_account_add_error", f"user={payload.username} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_account_add", f"user={payload.username}")
    return {"ok": True, "user": user}


@client_app.get("/databases")
def client_list_databases() -> dict[str, Any]:
    items = []
    for entry in list_entries(CLIENT_DB_PATH):
        items.append(
            {
                "db_name": entry["db_name"],
                "files": [],
                "created_at_utc": entry["created_at_utc"],
                "file_count": entry["file_count"],
                "total_size_bytes": entry["total_size_bytes"],
                "prep_status": entry["prep_status"],
            }
        )
    return {"ok": True, "databases": items}


@client_app.post("/databases/select")
def client_select_database(payload: DatabaseCreateRequest) -> dict[str, Any]:
    try:
        entry = get_entry(CLIENT_DB_PATH, payload.db_name)
        if entry is None:
            raise FileNotFoundError(f"database not found: {payload.db_name}")

        prep_status = str(entry.get("prep_status", "")).strip()
        server_addr = ""
        selected_scheme = "none"

        if prep_status in {"pirexx", "pirex+pirexx"}:
            server_addr = request_server_pirexx_sread(payload.db_name)
            set_selected_pirexx_database(payload.db_name, server_addr)
            selected_scheme = "pirexx"
        elif prep_status == "pirex":
            server_addr = request_server_pirex_sread(payload.db_name)
            set_selected_pirex_database(payload.db_name, server_addr)
            selected_scheme = "pirex"
    except Exception as exc:
        log_event("client_database_select_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_database_select", f"db={payload.db_name} scheme={selected_scheme} server={server_addr}")
    return {
        "ok": True,
        "db_name": payload.db_name,
        "server_addr": server_addr,
        "selected_scheme": selected_scheme,
        "prep_status": prep_status,
    }


@client_app.post("/databases")
def client_create_database(payload: DatabaseCreateRequest) -> dict[str, Any]:
    try:
        result = new_folder_client(payload.db_name)
    except Exception as exc:
        log_event("client_database_create_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_database_create", f"db={payload.db_name}")
    write_database_log(payload.db_name, "创建", "成功")
    return {
        "ok": True,
        "db_name": result["db_name"],
        "client_paths_ready": result["client_paths_ready"],
        "server_result": result["server_result"],
    }


@client_app.get("/databases/{db_name}/files")
def client_list_database_files(db_name: str) -> dict[str, Any]:
    try:
        files = list_client_manifest_files(db_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "db_name": db_name, "files": files}


@client_app.delete("/databases/{db_name}")
def client_delete_database(db_name: str) -> dict[str, Any]:
    try:
        stopped_jobs = _stop_client_preprocess_jobs_for_db(db_name)
        result = client_delete_db(db_name)
    except Exception as exc:
        log_event("client_database_delete_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_database_delete", f"db={db_name} stopped_jobs={stopped_jobs}")
    write_database_log(db_name, "删除", "成功")
    return {"ok": True, **result, "stopped_preprocess_jobs": stopped_jobs}


@client_app.get("/tmp-files")
def client_list_tmp_files() -> dict[str, Any]:
    try:
        files = list_tmp_files()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "files": files}


@client_app.post("/databases/{db_name}/tmp-files")
async def client_stage_tmp_files(db_name: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:
    try:
        payloads: list[tuple[str, bytes]] = []
        for upload in files:
            payloads.append((upload.filename or "unnamed.bin", await upload.read()))
        result = save_tmp_files(db_name, payloads)
    except Exception as exc:
        log_event("client_tmpdata_stage_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_tmpdata_stage", f"db={db_name} files={len(result['saved_files'])}")
    return {"ok": True, **result}


@client_app.post("/tmp-files/delete")
def client_delete_tmp_file(payload: TmpDeleteRequest) -> dict[str, Any]:
    try:
        remove_tmp_file(payload.file_name)
    except Exception as exc:
        log_event("client_tmpdata_delete_error", f"file={payload.file_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_tmpdata_delete", f"file={payload.file_name}")
    return {"ok": True, "file_name": payload.file_name}


@client_app.post("/databases/{db_name}/upload")
def client_upload_files(db_name: str) -> dict[str, Any]:
    try:
        payloads = load_tmp_files_for_upload(db_name)
        if not payloads:
            raise ValueError("no tmpdata files staged")
        result = upload_files(db_name, payloads)
        replace_entry_stats(
            CLIENT_DB_PATH,
            db_name,
            file_count=int(result.get("current_file_count", 0)),
            total_size_bytes=int(result.get("current_total_size_bytes", 0)),
        )
        clear_tmp_root()
    except Exception as exc:
        log_event("client_database_upload_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_database_upload", f"db={db_name} files={len(result.get('saved_files', []))}")
    write_database_log(db_name, "上传", "成功")
    return {
        "ok": True,
        "db_name": db_name,
        "saved_files": result.get("saved_files", []),
        "message": "上传成功",
    }


@client_app.post("/databases/{db_name}/pack")
def client_pack_database(db_name: str, force: bool = Query(True)) -> dict[str, Any]:
    try:
        result = call_json("POST", f"/databases/{db_name}/pack?force={'true' if force else 'false'}")
        manifest_local_path = download_manifest_to_client(db_name)
    except Exception as exc:
        log_event("client_database_pack_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_database_pack", f"db={db_name} manifest={manifest_local_path}")
    write_database_log(db_name, "打包", "成功")
    result["client_manifest_path"] = str(manifest_local_path)
    return result


@client_app.post("/pirexx/preprocess")
def client_pirexx_preprocess(payload: DatabaseCreateRequest) -> dict[str, Any]:
    print(f"[client][pirexx][preprocess] request db={payload.db_name}")
    try:
        result = run_client_pirexx_uprep(payload.db_name)
    except Exception as exc:
        print(f"[client][pirexx][preprocess] failed db={payload.db_name} error={exc}")
        log_event("client_pirexx_preprocess_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(
        f"[client][pirexx][preprocess] completed db={payload.db_name} "
        f"server_addr={result['server_addr']} elapsed_ms={result['preprocessing_elapsed_ms']} "
        f"manifest={result['manifest_local_path']}"
    )
    log_event("client_pirexx_preprocess", f"db={payload.db_name} manifest={result['manifest_local_path']}")
    return {
        "ok": True,
        "db_name": payload.db_name,
        "server_addr": result["server_addr"],
        "manifest_local_path": result["manifest_local_path"],
        "preprocessing_elapsed_ms": result["preprocessing_elapsed_ms"],
    }


@client_app.post("/pirex/preprocess")
def client_pirex_preprocess(payload: DatabaseCreateRequest) -> dict[str, Any]:
    print(f"[client][pirex][preprocess] request db={payload.db_name}")
    try:
        result = run_client_pirex_uprep(payload.db_name)
    except Exception as exc:
        print(f"[client][pirex][preprocess] failed db={payload.db_name} error={exc}")
        log_event("client_pirex_preprocess_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(
        f"[client][pirex][preprocess] completed db={payload.db_name} "
        f"server_addr={result['server_addr']} elapsed_ms={result['preprocessing_elapsed_ms']} "
        f"manifest={result['manifest_local_path']}"
    )
    log_event("client_pirex_preprocess", f"db={payload.db_name} manifest={result['manifest_local_path']}")
    write_database_log(payload.db_name, "预处理(pirex)", "成功")
    return {
        "ok": True,
        "db_name": payload.db_name,
        "server_addr": result["server_addr"],
        "manifest_local_path": result["manifest_local_path"],
        "preprocessing_elapsed_ms": result["preprocessing_elapsed_ms"],
    }


@client_app.post("/preprocess/jobs/start")
def client_start_preprocess_job(payload: PreprocessJobRequest) -> dict[str, Any]:
    try:
        job = _start_preprocess_job(payload.db_name, payload.scheme)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **job}


@client_app.get("/preprocess/jobs/status")
def client_preprocess_job_status(scheme: str = Query(...)) -> dict[str, Any]:
    try:
        normalized_scheme = _normalize_preprocess_scheme(scheme)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with _preprocess_job_lock:
        job = _serialize_preprocess_job(_preprocess_jobs.get(normalized_scheme))
    return {"ok": True, **job}


@client_app.post("/preprocess/jobs/cancel")
def client_cancel_preprocess_job(payload: PreprocessJobRequest) -> dict[str, Any]:
    try:
        job = _cancel_preprocess_job(payload.db_name, payload.scheme)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **job}


@client_app.post("/databases/{db_name}/unfinished-clear")
def client_unfinished_clear_database(db_name: str) -> dict[str, Any]:
    try:
        result = unfinished_clear(db_name)
    except Exception as exc:
        log_event("client_unfinished_clear_error", f"db={db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("client_unfinished_clear", f"db={db_name}")
    return {"ok": True, **result}


@client_app.post("/restore/direct")
def client_direct_restore(payload: RestoreRequest) -> dict[str, Any]:
    try:
        start = time.perf_counter()
        result = direct_restore(
            db_name=payload.db_name,
            file_id=payload.file_id,
            force=payload.force,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        query_log = write_query_log(
            query_username=payload.query_user,
            db_name=payload.db_name,
            file_name=payload.file_id,
            download_action="direct",
            download_result="success",
            avg_block_query_time_ms=None,
        )
        write_all_log(
            query_user=payload.query_user,
            db_name=payload.db_name,
            time_ms=elapsed_ms,
        )
    except Exception as exc:  # pragma: no cover - thin API wrapper
        write_query_log(
            query_username=payload.query_user,
            db_name=payload.db_name,
            file_name=payload.file_id,
            download_action="direct",
            download_result="failed",
            avg_block_query_time_ms=None,
        )
        log_event("restore_direct_error", f"db={payload.db_name} file={payload.file_id} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("restore_direct", f"db={payload.db_name} file={payload.file_id}")
    return {
        "ok": True,
        "db_name": result["db_name"],
        "file_id": result["file_id"],
        "output_path": str(result["output_path"]),
        "file_name": result.get("file_name", payload.file_id),
        "sha256": result["sha256"],
        "block_indices": result["block_indices"],
        "query_total_time_ms": round(elapsed_ms, 4),
    }


@server_app.post("/pirexx/sread/start_or_switch")
def server_start_or_switch_sread(payload: ServerStartRequest) -> dict[str, Any]:
    try:
        server_addr = ensure_server_pirexx_sread(payload.db_name)
    except Exception as exc:  # pragma: no cover - thin API wrapper
        log_event("sread_start_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("sread_start", f"db={payload.db_name} addr={server_addr}")
    return {"ok": True, "db_name": payload.db_name, "server_addr": server_addr}


@server_app.post("/pirexx/preprocess/start")
def server_start_pirexx_preprocess(payload: ServerStartRequest) -> dict[str, Any]:
    global _pirexx_sprep_state
    print(f"[server][pirexx][preprocess][start] request db={payload.db_name}")
    try:
        with _pirexx_sprep_lock:
            _pirexx_sprep_state, pack_result = ensure_pirexx_sprep(_pirexx_sprep_state, payload.db_name)
            server_addr = _pirexx_sprep_state.addr
    except Exception as exc:
        print(f"[server][pirexx][preprocess][start] failed db={payload.db_name} error={exc}")
        log_event("pirexx_preprocess_start_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(
        f"[server][pirexx][preprocess][start] ready db={payload.db_name} "
        f"server_addr={server_addr} manifest={pack_result['manifest_path']} "
        f"packed_data={pack_result['packed_data_path']}"
    )
    log_event("pirexx_preprocess_start", f"db={payload.db_name} addr={server_addr}")
    return {
        "ok": True,
        "db_name": payload.db_name,
        "server_addr": server_addr,
        "manifest_path": str(pack_result["manifest_path"]),
        "packed_data_path": str(pack_result["packed_data_path"]),
    }


@server_app.post("/pirexx/preprocess/finalize")
def server_finalize_pirexx_preprocess(payload: PreprocessFinalizeRequest) -> dict[str, Any]:
    global _pirexx_sprep_state
    print(f"[server][pirexx][preprocess][finalize] request db={payload.db_name} success={payload.success}")
    try:
        with _pirexx_sprep_lock:
            result = finalize_pirexx_sprep(
                _pirexx_sprep_state,
                payload.db_name,
                preprocess_succeeded=payload.success,
            )
            _pirexx_sprep_state = None
    except Exception as exc:
        print(f"[server][pirexx][preprocess][finalize] failed db={payload.db_name} error={exc}")
        log_event("pirexx_preprocess_finalize_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(
        f"[server][pirexx][preprocess][finalize] completed db={payload.db_name} "
        f"success={payload.success} stopped={result['stopped']} "
        f"manifest_deleted={result['server_manifest_deleted']} prep_status={result['prep_status']}"
    )
    log_event(
        "pirexx_preprocess_finalize",
        f"db={payload.db_name} success={payload.success} manifest_deleted={result['server_manifest_deleted']}",
    )
    return {"ok": True, **result}


@server_app.post("/pirex/preprocess/start")
def server_start_pirex_preprocess(payload: ServerStartRequest) -> dict[str, Any]:
    global _pirex_sprep_state
    print(f"[server][pirex][preprocess][start] request db={payload.db_name}")
    try:
        with _pirex_sprep_lock:
            _pirex_sprep_state, pack_result = ensure_pirex_sprep(_pirex_sprep_state, payload.db_name)
            server_addr = _pirex_sprep_state.addr
    except Exception as exc:
        print(f"[server][pirex][preprocess][start] failed db={payload.db_name} error={exc}")
        log_event("pirex_preprocess_start_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(
        f"[server][pirex][preprocess][start] ready db={payload.db_name} "
        f"server_addr={server_addr} manifest={pack_result['manifest_path']} "
        f"packed_data={pack_result['packed_data_path']}"
    )
    log_event("pirex_preprocess_start", f"db={payload.db_name} addr={server_addr}")
    return {
        "ok": True,
        "db_name": payload.db_name,
        "server_addr": server_addr,
        "manifest_path": str(pack_result["manifest_path"]),
        "packed_data_path": str(pack_result["packed_data_path"]),
    }


@server_app.post("/pirex/preprocess/finalize")
def server_finalize_pirex_preprocess(payload: PreprocessFinalizeRequest) -> dict[str, Any]:
    global _pirex_sprep_state
    print(f"[server][pirex][preprocess][finalize] request db={payload.db_name} success={payload.success}")
    try:
        with _pirex_sprep_lock:
            result = finalize_pirex_sprep(
                _pirex_sprep_state,
                payload.db_name,
                preprocess_succeeded=payload.success,
            )
            _pirex_sprep_state = None
    except Exception as exc:
        print(f"[server][pirex][preprocess][finalize] failed db={payload.db_name} error={exc}")
        log_event("pirex_preprocess_finalize_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    print(
        f"[server][pirex][preprocess][finalize] completed db={payload.db_name} "
        f"success={payload.success} stopped={result['stopped']} "
        f"manifest_deleted={result['server_manifest_deleted']} prep_status={result['prep_status']}"
    )
    log_event(
        "pirex_preprocess_finalize",
        f"db={payload.db_name} success={payload.success} manifest_deleted={result['server_manifest_deleted']}",
    )
    return {"ok": True, **result}


@server_app.post("/pirex/sread/start_or_switch")
def server_start_or_switch_pirex_sread(payload: ServerStartRequest) -> dict[str, Any]:
    try:
        server_addr = ensure_server_pirex_sread(payload.db_name)
    except Exception as exc:  # pragma: no cover - thin API wrapper
        log_event("pirex_sread_start_error", f"db={payload.db_name} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("pirex_sread_start", f"db={payload.db_name} addr={server_addr}")
    return {"ok": True, "db_name": payload.db_name, "server_addr": server_addr}


@server_app.post("/pirexx/sread/stop")
def server_stop_sread() -> dict[str, Any]:
    global _pirexx_sread_state
    with _sread_lock:
        previous = _pirexx_sread_state
        if previous is not None:
            stop_pirexx_sread(previous)
            _pirexx_sread_state = None

    log_event("sread_stop", f"stopped={previous is not None}")
    return {"ok": True, "stopped": previous is not None}


@server_app.post("/pirex/sread/stop")
def server_stop_pirex_sread() -> dict[str, Any]:
    global _pirex_sread_state
    with _pirex_sread_lock:
        previous = _pirex_sread_state
        if previous is not None:
            stop_pirex_sread(previous)
            _pirex_sread_state = None

    log_event("pirex_sread_stop", f"stopped={previous is not None}")
    return {"ok": True, "stopped": previous is not None}


@client_app.post("/restore/pirex")
def client_pirex_restore(payload: RestoreRequest) -> dict[str, Any]:
    try:
        selected_db_name, selected_server_addr = get_selected_pirex_database()
        if selected_db_name == payload.db_name and selected_server_addr:
            server_addr = selected_server_addr
        else:
            server_addr = request_server_pirex_sread(payload.db_name)
            set_selected_pirex_database(payload.db_name, server_addr)
        result = restore_pirex_file(
            db_name=payload.db_name,
            file_id=payload.file_id,
            connect_addr=server_addr,
            force=payload.force,
        )
        pirex_avg_block_query_delay_ms = compute_avg_block_query_delay_ms(str(result["uread_stdout"]))
        query_log = write_query_log(
            query_username=payload.query_user,
            db_name=payload.db_name,
            file_name=payload.file_id,
            download_action="pirex",
            download_result="success",
            avg_block_query_time_ms=pirex_avg_block_query_delay_ms,
        )
        write_all_log(
            query_user=payload.query_user,
            db_name=payload.db_name,
            time_ms=pirex_avg_block_query_delay_ms,
        )
    except Exception as exc:  # pragma: no cover - thin API wrapper
        write_query_log(
            query_username=payload.query_user,
            db_name=payload.db_name,
            file_name=payload.file_id,
            download_action="pirex",
            download_result="failed",
            avg_block_query_time_ms=None,
        )
        log_event("restore_pirex_error", f"db={payload.db_name} file={payload.file_id} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("restore_pirex", f"db={payload.db_name} file={payload.file_id} server={server_addr}")
    return {
        "ok": True,
        "db_name": result["db_name"],
        "file_id": result["file_id"],
        "output_path": str(result["output_path"]),
        "file_name": result.get("file_name", payload.file_id),
        "sha256": result["sha256"],
        "block_indices": result["block_indices"],
        "server_addr": server_addr,
        "pirex_avg_block_query_delay_ms": pirex_avg_block_query_delay_ms,
    }


@client_app.post("/restore/pirexx")
def client_pirexx_restore(payload: RestoreRequest) -> dict[str, Any]:
    try:
        selected_db_name, selected_server_addr = get_selected_pirexx_database()
        if selected_db_name == payload.db_name and selected_server_addr:
            server_addr = selected_server_addr
        else:
            server_addr = request_server_pirexx_sread(payload.db_name)
            set_selected_pirexx_database(payload.db_name, server_addr)
        result = restore_pirexx_file(
            db_name=payload.db_name,
            file_id=payload.file_id,
            connect_addr=server_addr,
            force=payload.force,
        )
        pirexx_avg_block_query_delay_ms = compute_avg_block_query_delay_ms(str(result["uread_stdout"]))
        query_log = write_query_log(
            query_username=payload.query_user,
            db_name=payload.db_name,
            file_name=payload.file_id,
            download_action="pirex+",
            download_result="success",
            avg_block_query_time_ms=pirexx_avg_block_query_delay_ms,
        )
        write_all_log(
            query_user=payload.query_user,
            db_name=payload.db_name,
            time_ms=pirexx_avg_block_query_delay_ms,
        )
    except Exception as exc:  # pragma: no cover - thin API wrapper
        write_query_log(
            query_username=payload.query_user,
            db_name=payload.db_name,
            file_name=payload.file_id,
            download_action="pirex+",
            download_result="failed",
            avg_block_query_time_ms=None,
        )
        log_event("restore_pirexx_error", f"db={payload.db_name} file={payload.file_id} error={exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_event("restore_pirexx", f"db={payload.db_name} file={payload.file_id} server={server_addr}")
    return {
        "ok": True,
        "db_name": result["db_name"],
        "file_id": result["file_id"],
        "output_path": str(result["output_path"]),
        "file_name": result.get("file_name", payload.file_id),
        "sha256": result["sha256"],
        "block_indices": result["block_indices"],
        "server_addr": server_addr,
        "pirexx_avg_block_query_delay_ms": pirexx_avg_block_query_delay_ms,
    }


@server_app.get("/")
def server_index() -> dict[str, str]:
    return {"message": "PIREXX server API ready"}


def run_client_api() -> None:
    uvicorn.run(client_app, host="127.0.0.1", port=8000)


def run_server_api() -> None:
    uvicorn.run(server_app, host="127.0.0.1", port=8001)


def main() -> None:
    server_thread = threading.Thread(target=run_server_api, daemon=True)
    server_thread.start()
    run_client_api()


if __name__ == "__main__":
    main()
