# CE-PIR
基于pirex适配到普通远程文件存储系统的项目


# Pirex 项目 Windows 平台使用指南

## 📋 目录

1. [环境要求](#环境要求)
2. [依赖安装](#依赖安装)
3. [secp256k1 库构建](#secp256k1-库构建)
4. [下载离散对数表](#下载离散对数表)
5. [项目配置与构建](#项目配置与构建)
6. [运行测试](#运行测试)
7. [常见问题](#常见问题)

---

## 环境要求

### 硬件要求

- **架构**: x86_64 (64位)
- **CPU**: 至少 8 核
- **内存**: 至少 16GB RAM
- **存储**: 至少 1TB（用于完整测试）

### 软件要求

- **操作系统**: Windows 10/11 (64位)
- **Rust**: nightly-2023-09-24
- **C/C++ 编译器**: MinGW-w64 (64位) 或 Visual Studio
- **CMake**: ≥ 3.16
- **Python**: 3.x

---

## 依赖安装

### 1. 安装 Rust

#### 方法 1: 使用 rustup（推荐）

访问 https://rustup.rs/ 下载并安装 rustup。

**或使用 PowerShell**:

```powershell
# 下载 rustup-init.exe
Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile rustup-init.exe

# 运行安装程序
.\rustup-init.exe
```

#### 安装指定版本的 Rust toolchain

```powershell
rustup toolchain install nightly-2023-09-24
rustup default nightly-2023-09-24

# 验证安装
rustc --version
```

---

### 2. 安装 C/C++ 编译器

#### 选项 A: 使用 MinGW-w64（推荐）

**推荐使用 QT MinGW 11.2.0**:

1. 如果已安装 QT，MinGW 通常位于：
   ```
   D:\Applications\tools\QT\Tools\mingw1120_64\bin
   ```

2. **或下载预编译版本**:
   - 访问: https://github.com/niXman/mingw-builds-binaries/releases
   - 下载: `x86_64-15.2.0-release-posix-seh-ucrt-rt_v13-rev0.7z`
   - 解压到任意目录，例如: `D:\Applications\tools\mingw\x86_64-mingw-w64`

3. **添加到系统 PATH**（可选，用于全局使用）:
   - 打开"系统属性" → "高级" → "环境变量"
   - 在"系统变量"的 `Path` 中添加 MinGW 的 `bin` 目录

#### 选项 B: 使用 Visual Studio

1. 下载 Visual Studio Installer: https://visualstudio.microsoft.com/downloads/
2. 安装 "Desktop development with C++" 工作负载
3. 确保包含 MSVC 编译器和 Windows SDK

---

### 3. 安装 CMake

1. 下载: https://cmake.org/download/
2. 选择 Windows x64 Installer
3. 安装时勾选 "Add CMake to system PATH"

**验证安装**:
```powershell
cmake --version
```

---

### 4. 安装 Python 3

1. 下载: https://www.python.org/downloads/
2. 安装时勾选 "Add Python to PATH"

**验证安装**:
```powershell
python --version
```

---

## secp256k1 库构建

### 前置检查

确保已安装：
- ✅ CMake (≥ 3.16)
- ✅ 64 位 C/C++ 编译器（MinGW 或 MSVC）

### 使用 MinGW 构建（推荐）

#### 步骤 1: 设置编译器环境

```powershell
# 使用 QT MinGW 11.2.0（根据您的实际路径调整）
$env:PATH = "D:\Applications\tools\QT\Tools\mingw1120_64\bin;$env:PATH"

# 验证编译器
gcc -dumpmachine
# 应该显示: x86_64-w64-mingw32
```

#### 步骤 2: 进入 secp256k1 目录

```powershell
cd D:\WorkStation\pythoncode\experiment-reproduction\windows\pirex-main\secp256k1
```

#### 步骤 3: 清理并创建构建目录

```powershell
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path build -Force | Out-Null
cd build
```

#### 步骤 4: 配置 CMake

**重要**: 如果系统中有多个 MinGW 安装，必须使用完整路径指定同一工具链的所有工具，避免混合使用不同工具链导致编译失败。

```powershell
# 设置 MinGW 路径（根据您的实际路径调整）
$mingw_path = "D:\Applications\tools\QT\Tools\mingw1120_64"

# 设置环境变量
$env:PATH = "$mingw_path\bin;$env:PATH"

# 配置 CMake（使用完整路径）
cmake .. -G "MinGW Makefiles" `
    -DCMAKE_BUILD_TYPE=Release `
    -DBUILD_SHARED_LIBS=OFF `
    -DCMAKE_C_COMPILER="$mingw_path\bin\gcc.exe" `
    -DCMAKE_CXX_COMPILER="$mingw_path\bin\g++.exe" `
    -DCMAKE_MAKE_PROGRAM="$mingw_path\bin\mingw32-make.exe" `
    -DSECP256K1_ENABLE_MODULE_ECDH=ON `
    -DSECP256K1_ENABLE_MODULE_EXTRAKEYS=ON `
    -DSECP256K1_ENABLE_MODULE_SCHNORRSIG=ON `
    -DSECP256K1_ENABLE_MODULE_MUSIG=ON `
    -DSECP256K1_ENABLE_MODULE_ELLSWIFT=ON `
    -DSECP256K1_BUILD_BENCHMARK=OFF `
    -DSECP256K1_BUILD_TESTS=OFF `
    -DSECP256K1_BUILD_EXHAUSTIVE_TESTS=OFF
```

**注意**: `-DCMAKE_MAKE_PROGRAM` 参数确保使用同一工具链的 make 程序，避免工具链混用问题。

#### 步骤 5: 构建

```powershell
cmake --build .
```

#### 步骤 6: 复制库文件到期望位置

```powershell
cd ..
# 创建 .libs 目录（如果不存在）
if (-not (Test-Path .libs)) {
    New-Item -ItemType Directory -Path .libs -Force | Out-Null
}

# 复制库文件
Copy-Item build\lib\libsecp256k1.a -Destination .libs\libsecp256k1.a -Force

# 验证
if (Test-Path .libs\libsecp256k1.a) {
    Write-Host "✓ secp256k1 库构建成功！" -ForegroundColor Green
    $lib = Get-Item .libs\libsecp256k1.a
    Write-Host "  大小: $([math]::Round($lib.Length / 1MB, 2)) MB" -ForegroundColor Cyan
}
```

### 使用 Visual Studio 构建

```powershell
# 打开 Developer Command Prompt for VS，然后：

cd D:\WorkStation\pythoncode\experiment-reproduction\windows\pirex-main\secp256k1
mkdir build
cd build

cmake .. -G "Visual Studio 17 2022" -A x64 `
    -DCMAKE_BUILD_TYPE=Release `
    -DBUILD_SHARED_LIBS=OFF `
    -DSECP256K1_ENABLE_MODULE_ECDH=ON `
    -DSECP256K1_ENABLE_MODULE_EXTRAKEYS=ON `
    -DSECP256K1_ENABLE_MODULE_SCHNORRSIG=ON `
    -DSECP256K1_ENABLE_MODULE_MUSIG=ON `
    -DSECP256K1_ENABLE_MODULE_ELLSWIFT=ON `
    -DSECP256K1_BUILD_BENCHMARK=OFF `
    -DSECP256K1_BUILD_TESTS=OFF `
    -DSECP256K1_BUILD_EXHAUSTIVE_TESTS=OFF

cmake --build . --config Release

# 复制库文件（MSVC 生成 .lib 文件）
cd ..
if (-not (Test-Path .libs)) {
    New-Item -ItemType Directory -Path .libs -Force | Out-Null
}
Copy-Item build\lib\Release\secp256k1.lib -Destination .libs\libsecp256k1.a -Force
```

---

## 下载离散对数表

`libsecp256k1.a` 需要一个预计算的离散对数表文件 `dlp.bin`。

### 下载方法

#### 方法 1: 使用 PowerShell（推荐）

```powershell
# 进入项目根目录
cd D:\WorkStation\pythoncode\experiment-reproduction\windows\pirex-main

# 下载 dlp.bin
$url = "https://www.dropbox.com/scl/fi/09dufxsm3qc4nnemdqgpv/dlp.bin?rlkey=rtcq1banfpl0cehdd2oa1b7zy&st=rfhznwre&dl=1"
Invoke-WebRequest -Uri $url -OutFile "dlp.bin"

# 移动到 utils 目录
if (-not (Test-Path utils)) {
    New-Item -ItemType Directory -Path utils -Force | Out-Null
}
Move-Item dlp.bin -Destination utils\dlp.bin -Force

# 验证
if (Test-Path utils\dlp.bin) {
    Write-Host "✓ dlp.bin 下载成功！" -ForegroundColor Green
    $dlp = Get-Item utils\dlp.bin
    Write-Host "  大小: $([math]::Round($dlp.Length / 1MB, 2)) MB" -ForegroundColor Cyan
}
```

#### 方法 2: 使用 curl（Windows 10+）

```powershell
cd D:\WorkStation\pythoncode\experiment-reproduction\windows\pirex-main

curl -L -o dlp.bin "https://www.dropbox.com/scl/fi/09dufxsm3qc4nnemdqgpv/dlp.bin?rlkey=rtcq1banfpl0cehdd2oa1b7zy&st=rfhznwre&dl=1"

# 移动到 utils 目录
if (-not (Test-Path utils)) {
    New-Item -ItemType Directory -Path utils -Force | Out-Null
}
Move-Item dlp.bin -Destination utils\dlp.bin -Force
```

#### 方法 3: 使用浏览器下载

1. 打开浏览器，访问以下链接：
   ```
   https://www.dropbox.com/scl/fi/09dufxsm3qc4nnemdqgpv/dlp.bin?rlkey=rtcq1banfpl0cehdd2oa1b7zy&st=rfhznwre&dl=1
   ```

2. 下载完成后，将文件移动到：
   ```
   D:\WorkStation\pythoncode\experiment-reproduction\windows\pirex-main\utils\dlp.bin
   ```

### 验证文件

```powershell
if (Test-Path utils\dlp.bin) {
    $dlp = Get-Item utils\dlp.bin
    Write-Host "✓ dlp.bin 文件存在" -ForegroundColor Green
    Write-Host "  位置: $($dlp.FullName)" -ForegroundColor Cyan
    Write-Host "  大小: $([math]::Round($dlp.Length / 1MB, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Host "✗ dlp.bin 文件不存在，请先下载" -ForegroundColor Red
}
```

---

## 项目配置与构建

### 步骤 1: 配置项目参数

```powershell
cd D:\WorkStation\pythoncode\experiment-reproduction\windows\pirex-main

# 配置数据库大小和块大小
# 格式: python config.py <chunks> <exponent>
# 示例: 64 块大小，2^22 数据库大小
python config.py 64 22
```

**参数说明**:
- `chunks`: 每个块包含的 64 字节块数量
  - `64` → 4 KiB (4096 字节)
  - `1024` → 64 KiB (65536 字节)
  - `4096` → 256 KiB (262144 字节)
- `exponent`: 数据库大小的指数（2 的幂）
  - `18` → 2^18 条记录
  - `22` → 2^22 条记录
  - `24` → 2^24 条记录

### 步骤 2: 构建 Rust 项目

```powershell
cargo build --release
```

**预期输出**:
```
warning: secp256k1 library path: <your_path>/secp256k1/.libs
   Compiling ...
   Finished release [optimized] target(s) in ...
```

### 步骤 3: 验证构建

```powershell
# 检查生成的可执行文件
Get-ChildItem target\release\*.exe | Select-Object Name

# 应该看到以下文件:
# - pirex_uread.exe
# - pirex_uprep.exe
# - pirex_sread.exe
# - pirex_sprep.exe
# - pirexx_uread.exe
# - pirexx_uprep.exe
# - pirexx_sread.exe
# - pirexx_sprep.exe
# - helper.exe
# 等等...
```

---

## 运行测试

### 初始化数据结构

在运行测试之前，需要先初始化客户端和服务器的数据结构：

```powershell
# 配置参数（根据测试规模选择）
python config.py 64 24

# 重新构建
cargo build --release

# 运行 helper 初始化数据
.\target\release\helper.exe
```

### 运行自动化测试

项目提供了 `control.py` 脚本用于自动化测试：

```powershell
# 小规模测试（推荐先运行）
python control.py pirex small

# 中等规模测试
python control.py pirex medium

# 大规模测试（需要大量存储空间）
python control.py pirex large
```

**注意**: Windows 版本的 `control.py` 已适配，支持 Windows 的进程管理命令。

### 手动运行测试

#### 离线阶段（Pirex）

**终端 1 - 服务器**:
```powershell
.\target\release\pirex_sprep.exe
```

**终端 2 - 客户端**:
```powershell
.\target\release\pirex_uprep.exe
```

#### 在线阶段（Pirex）

**终端 1 - 服务器**:
```powershell
.\target\release\pirex_sread.exe
```

**终端 2 - 客户端**:
```powershell
.\target\release\pirex_uread.exe
```

#### Pirex+ 方案

将上述命令中的 `pirex` 替换为 `pirexx` 即可。

---

## 常见问题

### 问题 1: 找不到 secp256k1 库

**错误信息**:
```
error: could not find native static library `secp256k1`
```

**解决方案**:
1. 确认库文件存在: `secp256k1\.libs\libsecp256k1.a`
2. 如果使用 MSVC 构建，确保文件名为 `libsecp256k1.a`（可能需要重命名）
3. 检查 `build.rs` 中的路径配置

### 问题 2: 编译器架构不匹配

**错误信息**:
```
error: size '2147483648' of array 'nodes' exceeds maximum object size '2147483647'
```

**原因**: 使用了 32 位编译器，但代码需要 64 位编译器。

**解决方案**:
- 确保使用 64 位 MinGW 或 MSVC
- 验证: `gcc -dumpmachine` 应显示 `x86_64-w64-mingw32`

### 问题 3: CMake 找不到编译器或工具链混用

**错误信息 1**:
```
CMake Error: No CMAKE_C_COMPILER could be found.
```

**错误信息 2** (工具链混用):
```
The C compiler "D:/path/to/msys2/ucrt64/bin/gcc.exe" is not able to compile a simple test program.
Run Build Command(s): D:/path/to/Dev-Cpp/MinGW64/bin/mingw32-make.exe
```

**原因**: 系统中有多个 MinGW 安装，CMake 自动选择了不同的工具链。

**解决方案**:
1. **使用完整路径明确指定工具链**:
   ```powershell
   $mingw_path = "D:\Applications\tools\QT\Tools\mingw1120_64"
   cmake .. -DCMAKE_C_COMPILER="$mingw_path\bin\gcc.exe" `
            -DCMAKE_MAKE_PROGRAM="$mingw_path\bin\mingw32-make.exe"
   ```

2. **清理 CMake 缓存**:
   ```powershell
   Remove-Item -Recurse -Force build
   ```

3. **临时设置 PATH**（仅包含需要的工具链）:
   ```powershell
   $env:PATH = "D:\Applications\tools\QT\Tools\mingw1120_64\bin;$env:PATH"
   ```

### 问题 4: Python 脚本执行失败

**错误信息**: `control.py` 无法找到或杀死进程

**解决方案**: 
- 确保已修改 `control.py` 以支持 Windows
- 或手动运行客户端和服务器程序

### 问题 5: dlp.bin 下载失败

**解决方案**:
1. 检查网络连接
2. 尝试使用浏览器直接下载
3. 检查文件是否完整（应该有数 MB 大小）

---

## 快速开始脚本

创建一个 `setup_windows.ps1` 脚本，一键完成所有设置：

```powershell
# setup_windows.ps1
Write-Host "=== Pirex 项目 Windows 环境设置 ===" -ForegroundColor Cyan

# 1. 检查 Rust
Write-Host "`n[1/5] 检查 Rust..." -ForegroundColor Yellow
if (Get-Command rustc -ErrorAction SilentlyContinue) {
    Write-Host "  ✓ Rust 已安装" -ForegroundColor Green
} else {
    Write-Host "  ✗ 请先安装 Rust" -ForegroundColor Red
    exit 1
}

# 2. 检查 CMake
Write-Host "`n[2/5] 检查 CMake..." -ForegroundColor Yellow
if (Get-Command cmake -ErrorAction SilentlyContinue) {
    Write-Host "  ✓ CMake 已安装" -ForegroundColor Green
} else {
    Write-Host "  ✗ 请先安装 CMake" -ForegroundColor Red
    exit 1
}

# 3. 检查 Python
Write-Host "`n[3/5] 检查 Python..." -ForegroundColor Yellow
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "  ✓ Python 已安装" -ForegroundColor Green
} else {
    Write-Host "  ✗ 请先安装 Python" -ForegroundColor Red
    exit 1
}

# 4. 下载 dlp.bin
Write-Host "`n[4/5] 检查 dlp.bin..." -ForegroundColor Yellow
if (Test-Path utils\dlp.bin) {
    Write-Host "  ✓ dlp.bin 已存在" -ForegroundColor Green
} else {
    Write-Host "  下载 dlp.bin..." -ForegroundColor Yellow
    $url = "https://www.dropbox.com/scl/fi/09dufxsm3qc4nnemdqgpv/dlp.bin?rlkey=rtcq1banfpl0cehdd2oa1b7zy&st=rfhznwre&dl=1"
    if (-not (Test-Path utils)) {
        New-Item -ItemType Directory -Path utils -Force | Out-Null
    }
    Invoke-WebRequest -Uri $url -OutFile utils\dlp.bin
    Write-Host "  ✓ dlp.bin 下载完成" -ForegroundColor Green
}

# 5. 检查 secp256k1 库
Write-Host "`n[5/5] 检查 secp256k1 库..." -ForegroundColor Yellow
if (Test-Path secp256k1\.libs\libsecp256k1.a) {
    Write-Host "  ✓ secp256k1 库已存在" -ForegroundColor Green
} else {
    Write-Host "  ⚠ secp256k1 库不存在，请先构建" -ForegroundColor Yellow
    Write-Host "  参考: secp256k1 库构建 章节" -ForegroundColor Yellow
}

Write-Host "`n=== 环境检查完成 ===" -ForegroundColor Green
```

---

## 目录结构

```
pirex-main/
├── secp256k1/              # secp256k1 加密库
│   ├── .libs/              # 构建输出目录
│   │   └── libsecp256k1.a  # 静态库文件
│   ├── build/              # CMake 构建目录
│   └── cmake/              # CMake 模块文件
├── src/                    # Rust 源代码
├── utils/                  # 辅助文件
│   └── dlp.bin            # 离散对数表（需下载）
├── results/                # 测试结果输出
├── config.py               # 配置脚本
├── control.py              # 自动化测试脚本
├── Cargo.toml              # Rust 项目配置
└── README.MD               # 原始文档（Linux 版本）
```

---

## 性能测试参数

### 测试用例配置

| 测试规模 | 块大小 (chunks) | 数据库大小 (exponent) | 存储需求 |
|---------|-----------------|---------------------|---------|
| **Small** | 64, 1024, 4096 | 18-22 | ~100 GB |
| **Medium** | 64, 1024, 4096 | 22-24 | ~1 TB |
| **Large** | 64, 1024, 4096 | 24-28 | ~1 TB+ |

### 运行测试

```powershell
# 小规模测试（推荐先运行）
python config.py 64 18
cargo build --release
.\target\release\helper.exe
python control.py pirex small

# 中等规模测试
python config.py 64 22
cargo build --release
.\target\release\helper.exe
python control.py pirex medium
```

---

## 参考文档

- **原始 README**: `README.MD` (Linux 版本)
- **Windows 重构方案**: `Windows重构方案.md`
- **CMake 构建问题诊断**: `secp256k1_CMake构建问题诊断.md`
- **构建脚本**: `构建secp256k1_使用64位MinGW.ps1`

---

## 技术支持

如遇到问题，请检查：

1. ✅ 所有依赖是否已正确安装
2. ✅ 编译器是否为 64 位版本
3. ✅ secp256k1 库是否已构建并位于正确位置
4. ✅ dlp.bin 文件是否已下载
5. ✅ 环境变量 PATH 是否正确配置

---

**文档版本**: 1.0  
**最后更新**: 2025-01-XX  
**适用平台**: Windows 10/11 (64位)

