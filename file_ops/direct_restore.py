from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from config import PIREXX_BLOCK_SIZE, packed_data_path
from file_ops.pirexx_dataset_restore import (
    build_indices,
    load_manifest,
    restore_pirexx_file,
    select_file,
    write_restored_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore a packed file directly from snapshot data.bin without PIREXX online recovery.",
    )
    parser.add_argument("db_name", help="Database name, for example bank2604.")
    parser.add_argument("file_id", help="Manifest file_id to restore. Current version uses flat file names.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing restored file.",
    )
    return parser.parse_args()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def resolve_packed_snapshot_path(db_name: str, manifest: dict[str, object]) -> Path:
    manifest_value = manifest.get("snapshot_data_path")
    if manifest_value:
        return Path(str(manifest_value))
    return packed_data_path(db_name)


def read_bytes_direct(db_name: str, manifest: dict[str, object], file_id: str) -> tuple[bytes, object]:
    entry = select_file(load_manifest(db_name)[1], file_id)
    snapshot_path = resolve_packed_snapshot_path(db_name, manifest)
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"packed snapshot file not found: {snapshot_path}")

    with snapshot_path.open("rb") as handle:
        handle.seek(entry.start_block * PIREXX_BLOCK_SIZE)
        packed = handle.read(entry.block_count * PIREXX_BLOCK_SIZE)

    expected = entry.block_count * PIREXX_BLOCK_SIZE
    if len(packed) != expected:
        raise IOError(
            f"short read from packed snapshot for {entry.file_id}: expected {expected} bytes, got {len(packed)}"
        )

    return packed[: entry.size_bytes], entry


def direct_restore(
    db_name: str,
    file_id: str,
    force: bool = False,
) -> dict[str, object]:
    manifest, files = load_manifest(db_name)
    entry = select_file(files, file_id)
    configured_block_size = int(manifest["block_size"])
    if configured_block_size != PIREXX_BLOCK_SIZE:
        raise ValueError(
            f"manifest block_size {configured_block_size} does not match current config block size {PIREXX_BLOCK_SIZE}"
        )

    content, _ = read_bytes_direct(db_name, manifest, file_id)
    actual_sha = sha256_bytes(content)
    if actual_sha != entry.sha256:
        raise ValueError(
            f"sha256 mismatch for {file_id}: expected {entry.sha256}, got {actual_sha}"
        )

    output_path = write_restored_file(entry, content, force)
    return {
        "db_name": db_name,
        "file_id": file_id,
        "output_path": output_path,
        "sha256": actual_sha,
        "block_indices": build_indices(entry),
        "file_name": entry.file_name,
        "content": content,
    }


def main() -> int:
    args = parse_args()
    result = direct_restore(
        db_name=args.db_name,
        file_id=args.file_id,
        force=args.force,
    )
    print(f"restored {result['file_id']} for database {result['db_name']}")
    print(f"output path: {result['output_path']}")
    print(f"block indices: {result['block_indices']}")
    print(f"sha256: {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
