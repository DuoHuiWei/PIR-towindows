from __future__ import annotations

from pathlib import Path

from file_ops.direct_restore import direct_restore
from file_ops.pirexx_dataset_restore import restore_pirexx_file


def restore_file_direct(db_name: str, file_id: str, force: bool = False) -> dict[str, object]:
    return direct_restore(db_name=db_name, file_id=file_id, force=force)


def restore_file_pirexx(db_name: str, file_id: str, server_addr: str, force: bool = False) -> dict[str, object]:
    return restore_pirexx_file(
        db_name=db_name,
        file_id=file_id,
        connect_addr=server_addr,
        force=force,
    )
