from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import PIREXX_SREAD_EXE
from utils.rust_ctrl import find_free_tcp_port, spawn_process, stop_process, wait_for_tcp_listen


@dataclass
class PirexxSreadState:
    db_name: str
    addr: str
    process: Any


def ensure_pirexx_sread(current_state: PirexxSreadState | None, db_name: str) -> PirexxSreadState:
    if current_state is not None and current_state.db_name == db_name and current_state.process.poll() is None:
        return current_state

    stop_pirexx_sread(current_state)

    if not PIREXX_SREAD_EXE.is_file():
        raise FileNotFoundError(f"pirexx_sread executable not found: {PIREXX_SREAD_EXE}")

    port = find_free_tcp_port()
    addr = f"127.0.0.1:{port}"
    process = spawn_process([str(PIREXX_SREAD_EXE), db_name, addr])
    if not wait_for_tcp_listen(addr, process):
        stdout, stderr = process.communicate(timeout=1)
        raise RuntimeError(
            f"pirexx_sread failed to start for {db_name} at {addr}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    return PirexxSreadState(db_name=db_name, addr=addr, process=process)


def stop_pirexx_sread(state: PirexxSreadState | None) -> None:
    if state is None:
        return
    stop_process(state.process)
