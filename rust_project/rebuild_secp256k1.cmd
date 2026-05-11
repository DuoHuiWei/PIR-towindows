@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || (
  echo [rebuild_secp256k1] failed: cannot enter repo root
  exit /b 1
)

set "CONFIG_FILE=%SCRIPT_DIR%toolchain.toml"
if not exist "%CONFIG_FILE%" (
  echo [rebuild_secp256k1] failed: missing config file "%CONFIG_FILE%"
  exit /b 1
)

set "ARG_NO_CONFIGURE=0"
set "ARG_VERBOSE=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--no-configure" (
  set "ARG_NO_CONFIGURE=1"
  shift
  goto parse_args
)
if /I "%~1"=="--verbose" (
  set "ARG_VERBOSE=1"
  shift
  goto parse_args
)

echo [rebuild_secp256k1] failed: unknown argument "%~1"
exit /b 1

:args_done
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%load_toolchain_env.ps1" "%CONFIG_FILE%"`) do (
  %%A
)

if not defined mingw_bin (
  echo [rebuild_secp256k1] failed: missing mingw_bin in toolchain.toml
  exit /b 1
)
if not defined cmake_bin (
  echo [rebuild_secp256k1] failed: missing cmake_bin in toolchain.toml
  exit /b 1
)
if not defined source_dir (
  echo [rebuild_secp256k1] failed: missing source_dir in toolchain.toml
  exit /b 1
)
if not defined build_dir (
  echo [rebuild_secp256k1] failed: missing build_dir in toolchain.toml
  exit /b 1
)
if not defined output_lib (
  echo [rebuild_secp256k1] failed: missing output_lib in toolchain.toml
  exit /b 1
)
if not defined linked_lib (
  echo [rebuild_secp256k1] failed: missing linked_lib in toolchain.toml
  exit /b 1
)
if not defined jobs set "jobs=1"

set "PATH=%mingw_bin%;%cmake_bin%;%PATH%"

if not exist "%mingw_bin%\gcc.exe" (
  echo [rebuild_secp256k1] failed: gcc.exe not found at "%mingw_bin%\gcc.exe"
  exit /b 1
)
if not exist "%mingw_bin%\g++.exe" (
  echo [rebuild_secp256k1] failed: g++.exe not found at "%mingw_bin%\g++.exe"
  exit /b 1
)
if not exist "%mingw_bin%\mingw32-make.exe" (
  echo [rebuild_secp256k1] failed: mingw32-make.exe not found at "%mingw_bin%\mingw32-make.exe"
  exit /b 1
)
if not exist "%cmake_bin%\cmake.exe" (
  echo [rebuild_secp256k1] failed: cmake.exe not found at "%cmake_bin%\cmake.exe"
  exit /b 1
)
if not exist "%source_dir%\CMakeLists.txt" (
  echo [rebuild_secp256k1] failed: secp256k1 source dir missing CMakeLists.txt at "%source_dir%"
  exit /b 1
)

if "%ARG_NO_CONFIGURE%"=="0" (
  echo [rebuild_secp256k1] configuring secp256k1 with CMake...
  set "CONFIGURE_CMD=cmake -S "%source_dir%" -B "%build_dir%" -G "MinGW Makefiles" -DCMAKE_C_COMPILER=%mingw_bin:\=/%/gcc.exe -DCMAKE_CXX_COMPILER=%mingw_bin:\=/%/g++.exe -DCMAKE_MAKE_PROGRAM=%mingw_bin:\=/%/mingw32-make.exe -DBUILD_SHARED_LIBS=OFF -DSECP256K1_BUILD_BENCHMARK=OFF -DSECP256K1_BUILD_TESTS=OFF -DSECP256K1_BUILD_EXHAUSTIVE_TESTS=OFF -DSECP256K1_BUILD_CTIME_TESTS=OFF -DSECP256K1_BUILD_EXAMPLES=OFF"
  if "%ARG_VERBOSE%"=="1" echo [rebuild_secp256k1] !CONFIGURE_CMD!
  cmake -S "%source_dir%" -B "%build_dir%" -G "MinGW Makefiles" ^
    -DCMAKE_C_COMPILER=%mingw_bin:\=/%/gcc.exe ^
    -DCMAKE_CXX_COMPILER=%mingw_bin:\=/%/g++.exe ^
    -DCMAKE_MAKE_PROGRAM=%mingw_bin:\=/%/mingw32-make.exe ^
    -DBUILD_SHARED_LIBS=OFF ^
    -DSECP256K1_BUILD_BENCHMARK=OFF ^
    -DSECP256K1_BUILD_TESTS=OFF ^
    -DSECP256K1_BUILD_EXHAUSTIVE_TESTS=OFF ^
    -DSECP256K1_BUILD_CTIME_TESTS=OFF ^
    -DSECP256K1_BUILD_EXAMPLES=OFF
  if errorlevel 1 (
    echo [rebuild_secp256k1] failed: CMake configure failed
    exit /b 1
  )
) else (
  echo [rebuild_secp256k1] skipping CMake configure by request
)

echo [rebuild_secp256k1] building secp256k1...
if "%ARG_VERBOSE%"=="1" echo [rebuild_secp256k1] mingw32-make -C "%build_dir%" -j%jobs%
mingw32-make -C "%build_dir%" -j%jobs%
if errorlevel 1 (
  echo [rebuild_secp256k1] failed: secp256k1 build failed
  exit /b 1
)

if not exist "%output_lib%" (
  echo [rebuild_secp256k1] failed: expected output library missing at "%output_lib%"
  exit /b 1
)

if not exist "%libs_dir%" mkdir "%libs_dir%"
copy /y "%output_lib%" "%linked_lib%" >nul
if errorlevel 1 (
  echo [rebuild_secp256k1] failed: unable to copy rebuilt library to "%linked_lib%"
  exit /b 1
)

for %%I in ("%output_lib%") do (
  set "OUTPUT_SIZE=%%~zI"
  set "OUTPUT_TIME=%%~tI"
)
for %%I in ("%linked_lib%") do (
  set "LINKED_SIZE=%%~zI"
  set "LINKED_TIME=%%~tI"
)

echo [rebuild_secp256k1] rebuilt library: "%output_lib%"
echo [rebuild_secp256k1] output size: !OUTPUT_SIZE! bytes
echo [rebuild_secp256k1] output time: !OUTPUT_TIME!
echo [rebuild_secp256k1] linked library: "%linked_lib%"
echo [rebuild_secp256k1] linked size: !LINKED_SIZE! bytes
echo [rebuild_secp256k1] linked time: !LINKED_TIME!
exit /b 0
