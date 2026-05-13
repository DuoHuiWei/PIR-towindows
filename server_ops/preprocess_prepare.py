from __future__ import annotations

from typing import Any

from database_registry import SERVER_DB_PATH, get_entry, remove_prep_status, update_entry_prep_status
from server_ops.pirex_sread_manager import PirexSreadState, stop_pirex_sread
from server_ops.server_pirex_sprep_manager import PirexSprepState, clear_server_pirex_state, stop_pirex_sprep
from server_ops.pirexx_sread_manager import PirexxSreadState, stop_pirexx_sread
from server_ops.server_pirexx_sprep_manager import PirexxSprepState, clear_server_pirexx_state, stop_pirexx_sprep


def _current_status(db_name: str) -> str:
    entry = get_entry(SERVER_DB_PATH, db_name)
    if not entry:
        raise FileNotFoundError(f"database not found: {db_name}")
    return str(entry.get("prep_status", "未完成"))


def prepare_server_preprocess(
    db_name: str,
    scheme: str,
    *,
    pirexx_sread_state: PirexxSreadState | None,
    pirex_sread_state: PirexSreadState | None,
    pirexx_sprep_state: PirexxSprepState | None,
    pirex_sprep_state: PirexSprepState | None,
) -> dict[str, Any]:
    current_status = _current_status(db_name)

    stopped = {
        "pirexx_sread": False,
        "pirex_sread": False,
        "pirexx_sprep": False,
        "pirex_sprep": False,
    }

    next_pirexx_sread_state = pirexx_sread_state
    next_pirex_sread_state = pirex_sread_state
    next_pirexx_sprep_state = pirexx_sprep_state
    next_pirex_sprep_state = pirex_sprep_state

    if pirexx_sread_state is not None and pirexx_sread_state.db_name == db_name:
        stop_pirexx_sread(pirexx_sread_state)
        next_pirexx_sread_state = None
        stopped["pirexx_sread"] = True

    if pirex_sread_state is not None and pirex_sread_state.db_name == db_name:
        stop_pirex_sread(pirex_sread_state)
        next_pirex_sread_state = None
        stopped["pirex_sread"] = True

    if pirexx_sprep_state is not None and pirexx_sprep_state.db_name == db_name:
        stop_pirexx_sprep(pirexx_sprep_state)
        clear_server_pirexx_state(db_name)
        next_pirexx_sprep_state = None
        stopped["pirexx_sprep"] = True
        current_status = remove_prep_status(current_status, "pirexx")

    if pirex_sprep_state is not None and pirex_sprep_state.db_name == db_name:
        stop_pirex_sprep(pirex_sprep_state)
        clear_server_pirex_state(db_name)
        next_pirex_sprep_state = None
        stopped["pirex_sprep"] = True
        current_status = remove_prep_status(current_status, "pirex")

    if scheme == "pirexx":
        clear_server_pirexx_state(db_name)
    else:
        clear_server_pirex_state(db_name)

    current_status = remove_prep_status(current_status, scheme)
    updated_entry = update_entry_prep_status(SERVER_DB_PATH, db_name, current_status)

    return {
        "db_name": db_name,
        "scheme": scheme,
        "stopped": stopped,
        "prep_status": updated_entry["prep_status"],
        "next_pirexx_sread_state": next_pirexx_sread_state,
        "next_pirex_sread_state": next_pirex_sread_state,
        "next_pirexx_sprep_state": next_pirexx_sprep_state,
        "next_pirex_sprep_state": next_pirex_sprep_state,
    }
