@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || (
  echo [build_gnu_nightly] failed: cannot enter repo root
  exit /b 1
)

set "CONFIG_FILE=%SCRIPT_DIR%toolchain.toml"
if not exist "%CONFIG_FILE%" (
  echo [build_gnu_nightly] failed: missing config file "%CONFIG_FILE%"
  exit /b 1
)

set "ARG_SKIP_SECP256K1=0"
set "ARG_RELEASE=0"
set "ARG_CHECK_ONLY=0"
set "ARG_VERBOSE=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--skip-secp256k1" (
  set "ARG_SKIP_SECP256K1=1"
  shift
  goto parse_args
)
if /I "%~1"=="--release" (
  set "ARG_RELEASE=1"
  shift
  goto parse_args
)
if /I "%~1"=="--check-only" (
  set "ARG_CHECK_ONLY=1"
  shift
  goto parse_args
)
if /I "%~1"=="--verbose" (
  set "ARG_VERBOSE=1"
  shift
  goto parse_args
)

echo [build_gnu_nightly] failed: unknown argument "%~1"
exit /b 1

:args_done
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%load_toolchain_env.ps1" "%CONFIG_FILE%"`) do (
  %%A
)

if not defined rustup_toolchain (
  echo [build_gnu_nightly] failed: missing rustup_toolchain in toolchain.toml
  exit /b 1
)
if not defined cargo_target (
  echo [build_gnu_nightly] failed: missing cargo_target in toolchain.toml
  exit /b 1
)
if not defined mingw_bin (
  echo [build_gnu_nightly] failed: missing mingw_bin in toolchain.toml
  exit /b 1
)
if not defined cmake_bin (
  echo [build_gnu_nightly] failed: missing cmake_bin in toolchain.toml
  exit /b 1
)
if not defined linked_lib (
  echo [build_gnu_nightly] failed: missing linked_lib in toolchain.toml
  exit /b 1
)
if not defined jobs set "jobs=1"
if not defined rebuild_secp256k1_by_default set "rebuild_secp256k1_by_default=true"
if not defined cargo_clean_before_build set "cargo_clean_before_build=true"

set "PATH=%mingw_bin%;%cmake_bin%;%PATH%"

where rustup >nul 2>nul || (
  echo [build_gnu_nightly] failed: rustup not found in PATH
  exit /b 1
)
where cargo >nul 2>nul || (
  echo [build_gnu_nightly] failed: cargo not found in PATH
  exit /b 1
)
where rustc >nul 2>nul || (
  echo [build_gnu_nightly] failed: rustc not found in PATH
  exit /b 1
)

echo [build_gnu_nightly] setting rustup override...
rustup override set %rustup_toolchain%
if errorlevel 1 (
  echo [build_gnu_nightly] failed: rustup override set failed
  exit /b 1
)

echo [build_gnu_nightly] ensuring cargo target %cargo_target%...
rustup target add %cargo_target% --toolchain %rustup_toolchain%
if errorlevel 1 (
  echo [build_gnu_nightly] failed: rustup target add failed
  exit /b 1
)

echo [build_gnu_nightly] current toolchain:
rustc -Vv
if errorlevel 1 exit /b 1
cargo -V
if errorlevel 1 exit /b 1
rustup show active-toolchain
if errorlevel 1 exit /b 1

for /f "usebackq delims=" %%A in (`rustup show active-toolchain`) do set "ACTIVE_TOOLCHAIN=%%A"
echo !ACTIVE_TOOLCHAIN! | findstr /I "msvc" >nul
if not errorlevel 1 (
  echo [build_gnu_nightly] failed: active toolchain is MSVC, GNU toolchain required
  exit /b 1
)

for %%I in ("%linked_lib%") do set "LINKED_LIB_TIME=%%~tI"
for %%I in ("secp256k1\src\secp256k1.c") do set "SECP_SOURCE_TIME=%%~tI"
if exist "%linked_lib%" (
  echo [build_gnu_nightly] secp256k1 source time: !SECP_SOURCE_TIME!
  echo [build_gnu_nightly] linked library time: !LINKED_LIB_TIME!
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$src = (Get-Item 'secp256k1\src\secp256k1.c').LastWriteTime; " ^
    "$lib = (Get-Item '%linked_lib%').LastWriteTime; " ^
    "if ($src -gt $lib) { exit 3 } else { exit 0 }"
  if errorlevel 3 (
    echo [build_gnu_nightly] warning: secp256k1 source may be newer than linked .libs library; consider rebuilding secp256k1
  )
) else (
  echo [build_gnu_nightly] warning: linked secp256k1 library missing at "%linked_lib%"
)

if /I "%ARG_CHECK_ONLY%"=="1" (
  echo [build_gnu_nightly] check-only complete
  exit /b 0
)

if /I "%ARG_SKIP_SECP256K1%"=="0" if /I "%rebuild_secp256k1_by_default%"=="true" (
  echo [build_gnu_nightly] rebuilding secp256k1 first...
  call "%SCRIPT_DIR%rebuild_secp256k1.cmd"
  if errorlevel 1 (
    echo [build_gnu_nightly] failed: secp256k1 rebuild step failed
    exit /b 1
  )
) else (
  echo [build_gnu_nightly] secp256k1 rebuild disabled by config
)

if not exist "%linked_lib%" (
  echo [build_gnu_nightly] failed: linked secp256k1 library missing at "%linked_lib%"
  exit /b 1
)

if /I "%cargo_clean_before_build%"=="true" (
  echo [build_gnu_nightly] running cargo clean...
  cargo clean
  if errorlevel 1 (
    echo [build_gnu_nightly] failed: cargo clean failed
    exit /b 1
  )
)

set "BUILD_PROFILE=debug"
set "BUILD_ARGS=build -j%jobs% --target %cargo_target%"
if "%ARG_RELEASE%"=="1" (
  set "BUILD_PROFILE=release"
  set "BUILD_ARGS=build -j%jobs% --target %cargo_target% --release"
)

echo [build_gnu_nightly] running cargo !BUILD_ARGS!...
if "%ARG_VERBOSE%"=="1" echo [build_gnu_nightly] cargo !BUILD_ARGS!
cargo !BUILD_ARGS!
if errorlevel 1 (
  echo [build_gnu_nightly] failed: cargo build failed
  exit /b 1
)

set "UREAD_EXE=target\%cargo_target%\%BUILD_PROFILE%\pirexx_uread.exe"
set "HELPER_EXE=target\%cargo_target%\%BUILD_PROFILE%\helper.exe"

if not exist "!UREAD_EXE!" (
  echo [build_gnu_nightly] failed: missing expected output "!UREAD_EXE!"
  exit /b 1
)
if not exist "!HELPER_EXE!" (
  echo [build_gnu_nightly] failed: missing expected output "!HELPER_EXE!"
  exit /b 1
)

for %%I in ("!UREAD_EXE!") do (
  set "UREAD_SIZE=%%~zI"
  set "UREAD_TIME=%%~tI"
)
for %%I in ("!HELPER_EXE!") do (
  set "HELPER_SIZE=%%~zI"
  set "HELPER_TIME=%%~tI"
)

echo [build_gnu_nightly] build complete
echo [build_gnu_nightly] output: !UREAD_EXE! ^(!UREAD_SIZE! bytes, !UREAD_TIME!^)
echo [build_gnu_nightly] output: !HELPER_EXE! ^(!HELPER_SIZE! bytes, !HELPER_TIME!^)
exit /b 0
