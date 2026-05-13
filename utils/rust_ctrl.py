from __future__ import annotations

import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

from config import RUST_PROJECT_DIR


def run_process(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd or RUST_PROJECT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def spawn_process(command: list[str], cwd: Path | None = None) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=cwd or RUST_PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def spawn_logged_process(
    command: list[str],
    log_path: Path,
    cwd: Path | None = None,
) -> subprocess.Popen[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8", newline="\n") as log_file:
        stamp = datetime.now().isoformat(timespec="seconds")
        log_file.write(f"[{stamp}] command: {' '.join(command)}\n")
        log_file.flush()

        return subprocess.Popen(
            command,
            cwd=cwd or RUST_PROJECT_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )


def read_process_log(log_path: Path) -> str:
    if not log_path.is_file():
        return ""
    return log_path.read_text(encoding="utf-8", errors="replace")


def split_host_port(addr: str) -> tuple[str, int]:
    host, port_text = addr.rsplit(":", 1)
    return host, int(port_text)


def find_free_tcp_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def is_tcp_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        except OSError:
            return True
        return False


def wait_for_tcp_listen(addr: str, process: subprocess.Popen[str], timeout_s: float = 15.0) -> bool:
    host, port = split_host_port(addr)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        if is_tcp_listening(host, port):
            return True
        time.sleep(0.2)
    return False


def stop_process(process: subprocess.Popen[str] | None, timeout_s: float = 5.0) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout_s)
