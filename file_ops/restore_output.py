from __future__ import annotations

from pathlib import Path

from config import recover_root


def resolve_restore_output_path(file_name: str, *, allow_collision_suffix: bool) -> Path:
    output_dir = recover_root()
    output_dir.mkdir(parents=True, exist_ok=True)

    candidate = output_dir / file_name
    if not candidate.exists():
        return candidate

    if not allow_collision_suffix:
        raise FileExistsError(f"restored file already exists: {candidate}")

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        renamed = output_dir / f"{stem}({index}){suffix}"
        if not renamed.exists():
            return renamed
        index += 1

