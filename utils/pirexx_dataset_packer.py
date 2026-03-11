#!/usr/bin/env python3
"""Pack a directory of real files into one fixed-size pirexx data image."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


BLOCK_SIZE = 4096
BLOCK_COUNT = 262144
DATA_SIZE_BYTES = BLOCK_SIZE * BLOCK_COUNT
CHUNK_SIZE = 1024 * 1024


@dataclass
class FileEntry:
    file_id: str
    relative_path: str
    size_bytes: int
    sha256: str
    start_block: int
    block_count: int
    end_block_exclusive: int
    tail_valid_bytes: int

    def to_manifest(self) -> dict[str, object]:
        return {
            "file_id": self.file_id,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "start_block": self.start_block,
            "block_count": self.block_count,
            "end_block_exclusive": self.end_block_exclusive,
            "tail_valid_bytes": self.tail_valid_bytes,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pack files under an input directory into pirexx data + manifest."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing source files to pack.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where data and manifest.json will be created.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output data/manifest files.",
    )
    return parser.parse_args()


def iter_files(input_dir: Path) -> Iterable[Path]:
    for path in sorted(p for p in input_dir.rglob("*") if p.is_file()):
        yield path


def relative_id(input_dir: Path, path: Path) -> str:
    return path.relative_to(input_dir).as_posix()


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
    return (size_bytes + BLOCK_SIZE - 1) // BLOCK_SIZE


def tail_valid_bytes(size_bytes: int, block_count: int) -> int:
    if block_count == 0:
        return 0
    remainder = size_bytes % BLOCK_SIZE
    return remainder if remainder != 0 else BLOCK_SIZE


def build_manifest_entries(input_dir: Path) -> tuple[list[FileEntry], int]:
    entries: list[FileEntry] = []
    next_block = 0

    for path in iter_files(input_dir):
        rel_path = relative_id(input_dir, path)
        size_bytes = path.stat().st_size
        file_blocks = blocks_for_size(size_bytes)

        if next_block + file_blocks > BLOCK_COUNT:
            raise ValueError(
                f"dataset exceeds pirexx capacity at {rel_path}: "
                f"requires {next_block + file_blocks} blocks, capacity is {BLOCK_COUNT}"
            )

        entry = FileEntry(
            file_id=rel_path,
            relative_path=rel_path,
            size_bytes=size_bytes,
            sha256=sha256_file(path),
            start_block=next_block,
            block_count=file_blocks,
            end_block_exclusive=next_block + file_blocks,
            tail_valid_bytes=tail_valid_bytes(size_bytes, file_blocks),
        )
        entries.append(entry)
        next_block += file_blocks

    return entries, next_block


def ensure_output_paths(output_dir: Path, force: bool) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "data"
    manifest_path = output_dir / "manifest.json"

    conflicts = [path for path in (data_path, manifest_path) if path.exists()]
    if conflicts and not force:
        names = ", ".join(path.name for path in conflicts)
        raise FileExistsError(f"output already exists: {names}; rerun with --force")

    return data_path, manifest_path


def pack_data_file(input_dir: Path, entries: list[FileEntry], data_path: Path) -> None:
    with data_path.open("wb") as data_file:
        data_file.truncate(DATA_SIZE_BYTES)

    with data_path.open("r+b") as data_file:
        for entry in entries:
            source_path = input_dir / Path(entry.relative_path)
            data_file.seek(entry.start_block * BLOCK_SIZE)

            with source_path.open("rb") as source_file:
                remaining = entry.size_bytes

                while remaining > 0:
                    to_read = min(BLOCK_SIZE, remaining)
                    chunk = source_file.read(to_read)
                    if len(chunk) != to_read:
                        raise IOError(
                            f"short read while packing {entry.relative_path}: "
                            f"expected {to_read} bytes, got {len(chunk)}"
                        )

                    if to_read < BLOCK_SIZE:
                        chunk = chunk + (b"\x00" * (BLOCK_SIZE - to_read))

                    data_file.write(chunk)
                    remaining -= to_read


def write_manifest(
    manifest_path: Path,
    input_dir: Path,
    entries: list[FileEntry],
    used_blocks: int,
) -> None:
    manifest = {
        "format_version": 1,
        "generator": "utils/pirexx_dataset_packer.py",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_root": str(input_dir.resolve()),
        "block_size": BLOCK_SIZE,
        "block_count": BLOCK_COUNT,
        "data_size_bytes": DATA_SIZE_BYTES,
        "used_blocks": used_blocks,
        "padding_policy": "zero-fill-tail-and-unused-blocks",
        "files": [entry.to_manifest() for entry in entries],
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not input_dir.is_dir():
        raise NotADirectoryError(f"input directory does not exist: {input_dir}")

    data_path, manifest_path = ensure_output_paths(output_dir, args.force)
    entries, used_blocks = build_manifest_entries(input_dir)
    pack_data_file(input_dir, entries, data_path)
    write_manifest(manifest_path, input_dir, entries, used_blocks)

    print(f"packed dataset from {input_dir}")
    print(f"created {data_path}")
    print(f"created {manifest_path}")
    print(f"files packed: {len(entries)}")
    print(f"used blocks: {used_blocks} / {BLOCK_COUNT}")
    print(f"unused blocks: {BLOCK_COUNT - used_blocks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
