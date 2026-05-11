from __future__ import annotations

import json
import uuid
from pathlib import Path
from urllib import error, request

from config import SERVER_API_BASE_URL, client_manifest_dir, manifest_path


def _api_url(path: str) -> str:
    return f"{SERVER_API_BASE_URL}{path}"


def _read_response_body(exc: error.HTTPError) -> str:
    return exc.read().decode("utf-8", errors="replace")


def call_json(method: str, path: str, payload: dict[str, object] | None = None, timeout: int = 60) -> dict[str, object]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    http_request = request.Request(
        url=_api_url(path),
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"server API returned HTTP {exc.code}: {_read_response_body(exc)}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"server API not reachable: {exc}") from exc


def upload_files(db_name: str, files: list[tuple[str, bytes, str]]) -> dict[str, object]:
    boundary = f"----PIRBoundary{uuid.uuid4().hex}"
    body = bytearray()

    for file_name, content, content_type in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="files"; filename="{Path(file_name).name}"\r\n'
                f"Content-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(content)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    http_request = request.Request(
        url=_api_url(f"/databases/{db_name}/upload"),
        data=bytes(body),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"server API returned HTTP {exc.code}: {_read_response_body(exc)}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"server API not reachable: {exc}") from exc


def download_manifest_to_client(db_name: str) -> Path:
    client_manifest_dir().mkdir(parents=True, exist_ok=True)
    target = manifest_path(db_name)
    http_request = request.Request(
        url=_api_url(f"/databases/{db_name}/manifest"),
        method="GET",
    )
    try:
        with request.urlopen(http_request, timeout=60) as response:
            target.write_bytes(response.read())
    except error.HTTPError as exc:
        raise RuntimeError(f"server API returned HTTP {exc.code}: {_read_response_body(exc)}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"server API not reachable: {exc}") from exc
    return target


def server_manifest_exists(db_name: str) -> bool:
    http_request = request.Request(
        url=_api_url(f"/databases/{db_name}/manifest"),
        method="GET",
    )
    try:
        with request.urlopen(http_request, timeout=30):
            return True
    except error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise RuntimeError(f"server API returned HTTP {exc.code}: {_read_response_body(exc)}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"server API not reachable: {exc}") from exc
