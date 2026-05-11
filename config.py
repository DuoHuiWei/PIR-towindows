from __future__ import annotations

from pathlib import Path


WORKSPACE_ROOT = Path(r"E:\pir-worktrees\new-work-v1")

# Server-side database layout
SERVER_DATA_ROOT = Path(r"rust_data\server-data")
SOURCE_DATA_DIR_NAME = "data"
SNAPSHOT_DIR_NAME = "snapshot"
PACKED_DATA_FILE_NAME = "data.bin"

# Client-side metadata and temporary block exports
CLIENT_MANIFEST_DIR = Path(r"rust_data\client-data\manifest")
CLIENT_DATA_ITEM_DIR = Path(r"rust_data\client-data\data_item")
CLIENT_LOG_DIR = Path(r"rust_data\client-data\log")
CLIENT_TMPDATA_DIR = Path(r"tmpdata")

# Final restored file output root
RECOVER_ROOT = Path("recover-file")

# Current PIREXX geometry
PIREXX_BLOCK_SIZE = 256 * 1024
PIREXX_BLOCK_COUNT = 256
PIREX_BLOCK_SIZE = PIREXX_BLOCK_SIZE
PIREX_BLOCK_COUNT = PIREXX_BLOCK_COUNT
SHOW_UPLOAD_LIMIT_HINT = False

# Rust invocation defaults
RUST_PROJECT_DIR = WORKSPACE_ROOT / "rust_project"
RUST_TARGET_RELEASE_DIR = RUST_PROJECT_DIR / r"target\x86_64-pc-windows-gnu\release"
RUST_SCHEME_BIN_DIR = RUST_PROJECT_DIR / "bin"


def _resolve_rust_binary(scheme_name: str, binary_name: str) -> Path:
    preferred = RUST_SCHEME_BIN_DIR / scheme_name / binary_name
    fallback = RUST_TARGET_RELEASE_DIR / binary_name
    return preferred if preferred.is_file() else fallback


PIREX_UREAD_EXE = _resolve_rust_binary("pirex", "pirex_uread.exe")
PIREX_SREAD_EXE = _resolve_rust_binary("pirex", "pirex_sread.exe")
PIREX_UPREP_EXE = _resolve_rust_binary("pirex", "pirex_uprep.exe")
PIREX_SPREP_EXE = _resolve_rust_binary("pirex", "pirex_sprep.exe")
PIREXX_UREAD_EXE = _resolve_rust_binary("pirexx", "pirexx_uread.exe")
PIREXX_SREAD_EXE = _resolve_rust_binary("pirexx", "pirexx_sread.exe")
PIREXX_UPREP_EXE = _resolve_rust_binary("pirexx", "pirexx_uprep.exe")
PIREXX_SPREP_EXE = _resolve_rust_binary("pirexx", "pirexx_sprep.exe")
HELPER_EXE = RUST_TARGET_RELEASE_DIR / "helper.exe"

PIREX_SERVER_ADDRESS = "127.0.0.1:52024"
PIREXX_SERVER_ADDRESS = "127.0.0.1:52014"
SERVER_API_BASE_URL = "http://127.0.0.1:8001"


def workspace_path(*parts: str) -> Path:
    return WORKSPACE_ROOT.joinpath(*parts)


def server_data_root() -> Path:
    return WORKSPACE_ROOT / SERVER_DATA_ROOT


def database_root(db_name: str) -> Path:
    return server_data_root() / db_name


def source_data_dir(db_name: str) -> Path:
    return database_root(db_name) / SOURCE_DATA_DIR_NAME


def snapshot_dir(db_name: str) -> Path:
    return database_root(db_name) / SNAPSHOT_DIR_NAME


def packed_data_path(db_name: str) -> Path:
    return snapshot_dir(db_name) / PACKED_DATA_FILE_NAME


def snapshot_manifest_path(db_name: str) -> Path:
    return snapshot_dir(db_name) / f"{db_name}_manifest.json"


def server_pirex_state_dir(db_name: str) -> Path:
    return database_root(db_name) / "state-pirex"


def server_pirexx_state_dir(db_name: str) -> Path:
    return database_root(db_name) / "state-pirexx"


def client_manifest_dir() -> Path:
    return WORKSPACE_ROOT / CLIENT_MANIFEST_DIR


def manifest_path(db_name: str) -> Path:
    return client_manifest_dir() / f"{db_name}_manifest.json"


def client_data_item_dir() -> Path:
    return WORKSPACE_ROOT / CLIENT_DATA_ITEM_DIR


def client_pirex_data_item_dir() -> Path:
    return WORKSPACE_ROOT / Path(r"rust_data\client-data\data_item_pirex")


def client_pirexx_data_item_dir() -> Path:
    return client_data_item_dir()


def client_log_dir() -> Path:
    return WORKSPACE_ROOT / CLIENT_LOG_DIR


def client_query_log_path() -> Path:
    return client_log_dir() / "qurey_log.json"


def client_user_manager_log_path() -> Path:
    return client_log_dir() / "user_manager_log.json"


def client_database_log_path() -> Path:
    return client_log_dir() / "database_log.json"


def client_all_log_path() -> Path:
    return client_log_dir() / "all_log.json"


def client_preprocessing_log_path() -> Path:
    return client_log_dir() / "preprocessing_log.json"


def client_tmpdata_root() -> Path:
    return WORKSPACE_ROOT / CLIENT_TMPDATA_DIR


def recover_root() -> Path:
    return WORKSPACE_ROOT / RECOVER_ROOT


def recover_db_dir(db_name: str) -> Path:
    return recover_root() / db_name


def pirexx_dataset_capacity_bytes() -> int:
    return PIREXX_BLOCK_SIZE * PIREXX_BLOCK_COUNT


def pirex_dataset_capacity_bytes() -> int:
    return PIREX_BLOCK_SIZE * PIREX_BLOCK_COUNT
