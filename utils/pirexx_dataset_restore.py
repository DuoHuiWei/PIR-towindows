#!/usr/bin/env python3
"""Restore packed files from a pirexx snapshot using manifest block ranges."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ManifestFile:
    file_id: str
    relative_path: str
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
            relative_path=str(payload["relative_path"]),
            size_bytes=int(payload["size_bytes"]),
            sha256=str(payload["sha256"]),
            start_block=int(payload["start_block"]),
            block_count=int(payload["block_count"]),
            end_block_exclusive=int(payload["end_block_exclusive"]),
            tail_valid_bytes=int(payload["tail_valid_bytes"]),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore one or more files from a pirexx snapshot manifest."
    )
    parser.add_argument(
        "--reader",
        choices=("direct", "pir"),
        default="direct",
        help="Read blocks directly from packed data or through pirexx_uread.",
    )
    parser.add_argument(
        "--snapshot-dir",
        required=True,
        help="Directory containing data and manifest.json.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where restored files will be written. Required unless --verify-only is set.",
    )
    parser.add_argument(
        "--file-id",
        action="append",
        default=[],
        help="Restore only the specified file_id. May be provided multiple times.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify reconstructed content without writing files to disk.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--state-dir",
        help="STATE_DIR to use when --reader pir is selected.",
    )
    parser.add_argument(
        "--uread-command",
        help="Command used to launch pirexx_uread in PIR mode.",
    )
    parser.add_argument(
        "--repo-root",
        help="Working directory used for the pirexx_uread command. Defaults to the repo root.",
    )
    return parser.parse_args()


def load_manifest(snapshot_dir: Path) -> tuple[dict[str, object], list[ManifestFile]]:
    manifest_path = snapshot_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [ManifestFile.from_dict(item) for item in payload["files"]]
    return payload, files


def select_files(files: list[ManifestFile], requested_ids: list[str]) -> list[ManifestFile]:
    if not requested_ids:
        return files

    by_id = {entry.file_id: entry for entry in files}
    missing = [file_id for file_id in requested_ids if file_id not in by_id]
    if missing:
        raise KeyError(f"unknown file_id values: {', '.join(missing)}")

    return [by_id[file_id] for file_id in requested_ids]


def read_bytes(data_file, block_size: int, entry: ManifestFile) -> bytes:
    if entry.block_count == 0:
        return b""

    data_file.seek(entry.start_block * block_size)
    packed = data_file.read(entry.block_count * block_size)
    if len(packed) != entry.block_count * block_size:
        raise IOError(
            f"short read for {entry.file_id}: expected {entry.block_count * block_size} bytes, got {len(packed)}"
        )
    return packed[: entry.size_bytes]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def ensure_output_path(output_dir: Path, entry: ManifestFile, force: bool) -> Path:
    target = output_dir / Path(entry.relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        raise FileExistsError(
            f"output file already exists: {target}; rerun with --force to overwrite"
        )
    return target


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_uread_command(repo_root: Path) -> str | None:
    exe = repo_root / "target" / "debug" / "pirexx_uread.exe"
    if exe.is_file():
        return str(exe)
    return None


def read_bytes_via_pir(
    repo_root: Path,
    state_dir: Path,
    uread_command: str,
    block_size: int,
    entry: ManifestFile,
) -> bytes:
    if entry.block_count == 0:
        return b""

    temp_dir = state_dir / "_pir_restore_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    chunks = bytearray()

    for index in range(entry.start_block, entry.end_block_exclusive):
        raw_path = temp_dir / f"block_{index}.bin"
        if raw_path.exists():
            raw_path.unlink()

        env = os.environ.copy()
        env["PIREXX_STATE_DIR"] = str(state_dir)
        env["PIREXX_TEST_INDICES"] = str(index)
        env["PIREXX_N_TEST"] = "1"
        env["PIREXX_ITEM_RAW_PATH"] = str(raw_path)

        result = subprocess.run(
            uread_command,
            cwd=repo_root,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"pirexx_uread failed for block {index}\n"
                f"command: {uread_command}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        if not raw_path.is_file():
            raise FileNotFoundError(
                f"pirexx_uread did not export raw block {index} to {raw_path}"
            )

        block = raw_path.read_bytes()
        if len(block) != block_size:
            raise ValueError(
                f"invalid raw block size for {index}: expected {block_size}, got {len(block)}"
            )

        chunks.extend(block)

    return bytes(chunks[: entry.size_bytes])


def main() -> int:
    args = parse_args()
    snapshot_dir = Path(args.snapshot_dir).resolve()
    if not snapshot_dir.is_dir():
        raise NotADirectoryError(f"snapshot directory does not exist: {snapshot_dir}")

    if not args.verify_only and not args.output_dir:
        raise ValueError("--output-dir is required unless --verify-only is set")

    if args.reader == "pir" and not args.state_dir:
        raise ValueError("--state-dir is required when --reader pir is selected")

    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    state_dir = Path(args.state_dir).resolve() if args.state_dir else None
    if state_dir is not None and not state_dir.is_dir():
        raise NotADirectoryError(f"state directory does not exist: {state_dir}")

    uread_command = args.uread_command
    if args.reader == "pir" and not uread_command:
        uread_command = default_uread_command(repo_root)
        if not uread_command:
            raise ValueError(
                "no default pirexx_uread executable found; provide --uread-command explicitly"
            )

    manifest, files = load_manifest(snapshot_dir)
    selected = select_files(files, args.file_id)
    block_size = int(manifest["block_size"])
    data_path = snapshot_dir / "data"

    restored_count = 0
    verified_count = 0

    data_file = data_path.open("rb") if args.reader == "direct" else None

    try:
        for entry in selected:
            if args.reader == "direct":
                assert data_file is not None
                content = read_bytes(data_file, block_size, entry)
            else:
                assert state_dir is not None
                assert uread_command is not None
                content = read_bytes_via_pir(
                    repo_root=repo_root,
                    state_dir=state_dir,
                    uread_command=uread_command,
                    block_size=block_size,
                    entry=entry,
                )

            actual_sha = sha256_bytes(content)
            verified = actual_sha == entry.sha256

            if not verified:
                raise ValueError(
                    f"sha256 mismatch for {entry.file_id}: expected {entry.sha256}, got {actual_sha}"
                )

            if output_dir is not None and not args.verify_only:
                target = ensure_output_path(output_dir, entry, args.force)
                target.write_bytes(content)
                restored_count += 1
                print(f"restored {entry.file_id} -> {target}")
            else:
                print(f"verified {entry.file_id}")

            verified_count += 1
    finally:
        if data_file is not None:
            data_file.close()

        if args.reader == "pir" and state_dir is not None:
            temp_dir = state_dir / "_pir_restore_tmp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    print(f"verified files: {verified_count}")
    if not args.verify_only:
        print(f"restored files: {restored_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
