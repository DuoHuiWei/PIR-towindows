from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
TARGET_RELEASE_DIR = PROJECT_DIR / "target" / "x86_64-pc-windows-gnu" / "release"
SCHEME_BIN_DIR = PROJECT_DIR / "bin"

SCHEME_CONFIG = {
    "pirex": {
        "config_args": ["4096", "8"],
        "bins": ["pirex_uread.exe", "pirex_sread.exe", "pirex_uprep.exe", "pirex_sprep.exe", "helper.exe"],
    },
    "pirexx": {
        "config_args": ["4096", "8"],
        "bins": ["pirexx_uread.exe", "pirexx_sread.exe", "pirexx_uprep.exe", "pirexx_sprep.exe", "helper.exe"],
    },
}


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=PROJECT_DIR, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def build_scheme(scheme: str) -> None:
    if scheme not in SCHEME_CONFIG:
        raise SystemExit(f"unsupported scheme: {scheme}")

    config = SCHEME_CONFIG[scheme]
    run([sys.executable, "config.py", *config["config_args"]])
    run(["cargo", "build", "--release"])

    target_dir = SCHEME_BIN_DIR / scheme
    target_dir.mkdir(parents=True, exist_ok=True)
    for binary_name in config["bins"]:
        source = TARGET_RELEASE_DIR / binary_name
        if not source.is_file():
            raise SystemExit(f"missing built binary: {source}")
        shutil.copy2(source, target_dir / binary_name)

    print(f"built {scheme} binaries into {target_dir}")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python build_scheme_bins.py <pirex|pirexx>")
    build_scheme(sys.argv[1].strip().lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
