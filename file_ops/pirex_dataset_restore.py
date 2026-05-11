from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import (
    PIREX_BLOCK_SIZE,
    PIREX_SERVER_ADDRESS,
    PIREX_UREAD_EXE,
    RUST_PROJECT_DIR,
    client_pirex_data_item_dir,
    manifest_path,
)
from file_ops.block_clear import clear_block_dir
from file_ops.restore_output import resolve_restore_output_path


@dataclass
class ManifestFile:
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

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ManifestFile":
        return cls(
            file_id=str(payload["file_id"]),
            file_name=str(payload["file_name"]),
            extension=str(payload.get("extension", "")),
            file_type=str(payload.get("file_type", "")),
            size_bytes=int(payload["size_bytes"]),
            sha256=str(payload["sha256"]),
            start_block=int(payload["start_block"]),
            block_count=int(payload["block_count"]),
            end_block_exclusive=int(payload["end_block_exclusive"]),
            tail_valid_bytes=int(payload["tail_valid_bytes"]),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore a packed file from PIREX blocks using the client-side manifest.",
    )
    parser.add_argument("db_name", help="Database name, for example bank2604.")
    parser.add_argument("file_id", help="Manifest file_id to restore.")
    parser.add_argument(
        "--connect-addr",
        default=PIREX_SERVER_ADDRESS,
        help="Runtime PIREX sread address, default comes from config.",
    )
    parser.add_argument(
        "--uread-command",
        help="Explicit pirex_uread executable path. Defaults to config.PIREX_UREAD_EXE.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing restored file.",
    )
    return parser.parse_args()


def load_manifest(db_name: str) -> tuple[dict[str, object], list[ManifestFile]]:
    path = manifest_path(db_name)
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    files = [ManifestFile.from_dict(item) for item in payload["files"]]
    return payload, files


def select_file(files: list[ManifestFile], file_id: str) -> ManifestFile:
    for entry in files:
        if entry.file_id == file_id:
            return entry
    raise KeyError(f"file_id not found in manifest: {file_id}")


def build_indices(entry: ManifestFile) -> list[int]:
    return list(range(entry.start_block, entry.end_block_exclusive))


def run_pirex_uread(
    db_name: str,
    indices: list[int],
    connect_addr: str,
    uread_command: Path,
) -> subprocess.CompletedProcess[str]:
    if not uread_command.is_file():
        raise FileNotFoundError(f"pirex_uread executable not found: {uread_command}")

    env = os.environ.copy()
    env["PIREX_TEST_INDICES"] = ",".join(str(index) for index in indices)
    env["PIREX_N_TEST"] = "1"

    return subprocess.run(
        [str(uread_command), db_name, connect_addr],
        cwd=RUST_PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def read_exported_blocks(indices: list[int], expected_block_size: int) -> bytes:
    directory = client_pirex_data_item_dir()
    chunks = bytearray()

    for index in indices:
        block_path = directory / f"block_{index}.bin"
        if not block_path.is_file():
            raise FileNotFoundError(f"missing exported block: {block_path}")

        block = block_path.read_bytes()
        if len(block) != expected_block_size:
            raise ValueError(
                f"invalid block size for {block_path.name}: expected {expected_block_size}, got {len(block)}"
            )
        chunks.extend(block)

    return bytes(chunks)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def restore_pirex_file(
    db_name: str,
    file_id: str,
    connect_addr: str = PIREX_SERVER_ADDRESS,
    uread_command: Path = PIREX_UREAD_EXE,
    force: bool = False,
) -> dict[str, object]:
    manifest, files = load_manifest(db_name)
    entry = select_file(files, file_id)
    configured_block_size = int(manifest["block_size"])
    if configured_block_size != PIREX_BLOCK_SIZE:
        raise ValueError(
            f"manifest block_size {configured_block_size} does not match current PIREX block size {PIREX_BLOCK_SIZE}"
        )

    indices = build_indices(entry)
    clear_block_dir(client_pirex_data_item_dir())

    result = run_pirex_uread(db_name, indices, connect_addr, Path(uread_command))
    if result.returncode != 0:
        raise RuntimeError(
            f"pirex_uread failed for {file_id}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    packed = read_exported_blocks(indices, configured_block_size)
    content = packed[: entry.size_bytes]
    actual_sha = sha256_bytes(content)
    if actual_sha != entry.sha256:
        raise ValueError(
            f"sha256 mismatch for {file_id}: expected {entry.sha256}, got {actual_sha}"
        )

    output_path = resolve_restore_output_path(entry.file_name, allow_collision_suffix=force)
    output_path.write_bytes(content)
    return {
        "db_name": db_name,
        "file_id": file_id,
        "output_path": output_path,
        "sha256": actual_sha,
        "block_indices": indices,
        "uread_stdout": result.stdout,
        "file_name": entry.file_name,
        "content": content,
    }


def main() -> int:
    args = parse_args()
    result = restore_pirex_file(
        db_name=args.db_name,
        file_id=args.file_id,
        connect_addr=args.connect_addr,
        uread_command=Path(args.uread_command) if args.uread_command else PIREX_UREAD_EXE,
        force=args.force,
    )
    print(f"restored {result['file_id']} for database {result['db_name']}")
    print(f"output path: {result['output_path']}")
    print(f"block indices: {result['block_indices']}")
    print(f"sha256: {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
