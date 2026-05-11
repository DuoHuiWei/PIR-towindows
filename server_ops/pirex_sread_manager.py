from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import PIREX_SREAD_EXE
from utils.rust_ctrl import find_free_tcp_port, spawn_process, stop_process, wait_for_tcp_listen


@dataclass
class PirexSreadState:
    db_name: str
    addr: str
    process: Any


def ensure_pirex_sread(current_state: PirexSreadState | None, db_name: str) -> PirexSreadState:
    if current_state is not None and current_state.db_name == db_name and current_state.process.poll() is None:
        return current_state

    stop_pirex_sread(current_state)

    if not PIREX_SREAD_EXE.is_file():
        raise FileNotFoundError(f"pirex_sread executable not found: {PIREX_SREAD_EXE}")

    port = find_free_tcp_port()
    addr = f"127.0.0.1:{port}"
    process = spawn_process([str(PIREX_SREAD_EXE), db_name, addr])
    if not wait_for_tcp_listen(addr, process):
        stdout, stderr = process.communicate(timeout=1)
        raise RuntimeError(
            f"pirex_sread failed to start for {db_name} at {addr}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    return PirexSreadState(db_name=db_name, addr=addr, process=process)


def stop_pirex_sread(state: PirexSreadState | None) -> None:
    if state is None:
        return
    stop_process(state.process)
