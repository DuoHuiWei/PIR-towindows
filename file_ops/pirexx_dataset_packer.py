from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import (
    PIREXX_BLOCK_COUNT,
    PIREXX_BLOCK_SIZE,
    packed_data_path,
    snapshot_dir,
    snapshot_manifest_path,
    source_data_dir,
)


CHUNK_SIZE = 1024 * 1024


@dataclass
class FileEntry:
    file_id: str
    file_name: str
    extension: str
    file_type: str
    size_bytes: int
    sha256: str
    start_block: int
    block_count: int
    end_block_exclusive: int
    tail_valid_bytes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pack flat files from a database data directory into pirexx snapshot data.bin + manifest.",
    )
    parser.add_argument("db_name", help="Database name, for example bank2604.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing packed data and manifest.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def blocks_for_size(size_bytes: int) -> int:
    if size_bytes == 0:
        return 0
    return (size_bytes + PIREXX_BLOCK_SIZE - 1) // PIREXX_BLOCK_SIZE


def tail_valid_bytes(size_bytes: int, block_count: int) -> int:
    if block_count == 0:
        return 0
    remainder = size_bytes % PIREXX_BLOCK_SIZE
    return remainder if remainder else PIREXX_BLOCK_SIZE


def collect_source_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise NotADirectoryError(f"source data directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"source data path is not a directory: {input_dir}")

    subdirs = sorted(path for path in input_dir.iterdir() if path.is_dir())
    if subdirs:
        names = ", ".join(path.name for path in subdirs)
        raise ValueError(
            f"nested directories are not supported in {input_dir}; found subdirectories: {names}"
        )

    files = sorted(path for path in input_dir.iterdir() if path.is_file())
    return files


def build_manifest_entries(files: list[Path]) -> tuple[list[FileEntry], int]:
    entries: list[FileEntry] = []
    next_block = 0

    for path in files:
        size_bytes = path.stat().st_size
        block_count = blocks_for_size(size_bytes)

        if next_block + block_count > PIREXX_BLOCK_COUNT:
            raise ValueError(
                f"dataset exceeds configured capacity at {path.name}: "
                f"requires {next_block + block_count} blocks, capacity is {PIREXX_BLOCK_COUNT}"
            )

        suffix = path.suffix.lower()
        entry = FileEntry(
            file_id=path.name,
            file_name=path.name,
            extension=suffix,
            file_type=suffix[1:] if suffix.startswith(".") else suffix,
            size_bytes=size_bytes,
            sha256=sha256_file(path),
            start_block=next_block,
            block_count=block_count,
            end_block_exclusive=next_block + block_count,
            tail_valid_bytes=tail_valid_bytes(size_bytes, block_count),
        )
        entries.append(entry)
        next_block += block_count

    return entries, next_block


def ensure_output_paths(db_name: str, force: bool) -> tuple[Path, Path]:
    snapshot = snapshot_dir(db_name)
    snapshot.mkdir(parents=True, exist_ok=True)

    packed_path = packed_data_path(db_name)
    manifest_out = snapshot_manifest_path(db_name)

    conflicts = [path for path in (packed_path, manifest_out) if path.exists()]
    if conflicts and not force:
        names = ", ".join(str(path) for path in conflicts)
        raise FileExistsError(f"output already exists: {names}; rerun with --force")

    return packed_path, manifest_out


def pack_data_file(files: list[Path], entries: list[FileEntry], output_path: Path) -> None:
    total_size = PIREXX_BLOCK_SIZE * PIREXX_BLOCK_COUNT
    with output_path.open("wb") as handle:
        handle.truncate(total_size)

    by_name = {path.name: path for path in files}
    with output_path.open("r+b") as handle:
        for entry in entries:
            source_path = by_name[entry.file_name]
            handle.seek(entry.start_block * PIREXX_BLOCK_SIZE)

            with source_path.open("rb") as source:
                remaining = entry.size_bytes
                while remaining > 0:
                    to_read = min(PIREXX_BLOCK_SIZE, remaining)
                    chunk = source.read(to_read)
                    if len(chunk) != to_read:
                        raise IOError(
                            f"short read while packing {entry.file_name}: "
                            f"expected {to_read} bytes, got {len(chunk)}"
                        )

                    if to_read < PIREXX_BLOCK_SIZE:
                        chunk += b"\x00" * (PIREXX_BLOCK_SIZE - to_read)

                    handle.write(chunk)
                    remaining -= to_read


def write_manifest(db_name: str, input_dir: Path, entries: list[FileEntry], used_blocks: int) -> Path:
    output_path = snapshot_manifest_path(db_name)
    payload = {
        "db_name": db_name,
        "format_version": 1,
        "generator": "file_ops/pirexx_dataset_packer.py",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_root": str(input_dir.resolve()),
        "snapshot_data_path": str(packed_data_path(db_name).resolve()),
        "block_size": PIREXX_BLOCK_SIZE,
        "block_count": PIREXX_BLOCK_COUNT,
        "data_size_bytes": PIREXX_BLOCK_SIZE * PIREXX_BLOCK_COUNT,
        "used_blocks": used_blocks,
        "padding_policy": "zero-fill-tail-and-unused-blocks",
        "files": [asdict(entry) for entry in entries],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return output_path


def pack_database(db_name: str, force: bool = False) -> dict[str, object]:
    input_dir = source_data_dir(db_name)
    files = collect_source_files(input_dir)
    entries, used_blocks = build_manifest_entries(files)
    packed_path, manifest_out = ensure_output_paths(db_name, force)
    pack_data_file(files, entries, packed_path)
    write_manifest(db_name, input_dir, entries, used_blocks)

    return {
        "db_name": db_name,
        "input_dir": input_dir,
        "packed_data_path": packed_path,
        "manifest_path": manifest_out,
        "files_packed": len(entries),
        "used_blocks": used_blocks,
        "unused_blocks": PIREXX_BLOCK_COUNT - used_blocks,
    }


def main() -> int:
    args = parse_args()
    result = pack_database(args.db_name, force=args.force)
    print(f"packed dataset for {result['db_name']}")
    print(f"source dir: {result['input_dir']}")
    print(f"packed data: {result['packed_data_path']}")
    print(f"manifest: {result['manifest_path']}")
    print(f"files packed: {result['files_packed']}")
    print(f"used blocks: {result['used_blocks']} / {PIREXX_BLOCK_COUNT}")
    print(f"unused blocks: {result['unused_blocks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
