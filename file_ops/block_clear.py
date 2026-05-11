from __future__ import annotations

from pathlib import Path

from config import client_data_item_dir


def clear_block_dir(target_dir: Path | None = None) -> int:
    directory = target_dir or client_data_item_dir()
    directory.mkdir(parents=True, exist_ok=True)

    removed = 0
    for path in directory.glob("*.bin"):
        if path.is_file():
            path.unlink()
            removed += 1

    return removed


if __name__ == "__main__":
    removed_count = clear_block_dir()
    print(f"cleared {removed_count} block files from {client_data_item_dir()}")
