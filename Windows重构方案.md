# Pirex 项目 Windows 平台重构方案

## 1. 项目环境分析

### 1.1 当前环境配置

**项目类型**: Rust + C/C++ 混合项目

**主要组件**:
- **Rust 主程序**: 使用 Cargo 构建，包含多个二进制目标
- **C++ 辅助代码**: `utils/helper.cpp` - 使用 OpenMP、AVX2 指令集
- **C 加密库**: `secp256k1` - 需要编译为静态库
- **Python 脚本**: `config.py`, `control.py` - 用于配置和自动化测试

**当前平台假设**:
- Linux/Unix 系统（使用 `g++`, `make`, `autotools`）
- Unix shell 脚本（`autogen.sh`）
- Unix 系统调用（`sched_getcpu()`, `sched.h`）
- Unix 工具（`lsof`, `kill`）

### 1.2 关键依赖

**Rust 依赖** (Cargo.toml):
- `cc = "1.0"` - C/C++ 编译绑定
- `aes = "0.8.3"`
- `bitvec = "1.0.1"`
- `memmap = "0.7"`
- `packed_simd = "0.3.9"`
- `rand = "0.8.5"`
- `secp256k1 = "0.28.1"`

**C/C++ 依赖**:
- OpenMP (多线程支持)
- AVX2/AVX512 (SIMD 指令集)
- secp256k1 静态库

**构建工具依赖**:
- Rust toolchain (nightly-2023-09-24)
- C/C++ 编译器 (g++/cl.exe)
- CMake 或 autotools (用于 secp256k1)
- Python 3

---

## 2. Windows 平台适配问题分析

### 2.1 主要问题清单

| 问题类型 | 文件位置 | 问题描述 | 影响程度 |
|---------|---------|---------|---------|
| **C++ 编译器设置** | `src/build.rs` | 硬编码 `g++`，Windows 需 MSVC/MinGW | 🔴 高 |
| **OpenMP 链接** | `src/build.rs` | 链接 `gomp` (GNU OpenMP)，Windows 需不同库 | 🔴 高 |
| **系统调用** | `utils/helper.cpp` | 使用 `sched_getcpu()`, `sched.h` (Linux 特定) | 🔴 高 |
| **路径分隔符** | `src/build.rs` | 使用 `/` 路径，Windows 应支持 `\` | 🟡 中 |
| **进程管理** | `control.py` | 使用 `lsof`, `kill` (Unix 命令) | 🟡 中 |
| **secp256k1 构建** | `secp256k1/` | 使用 autotools，Windows 需 CMake | 🔴 高 |
| **Shell 脚本** | `secp256k1/autogen.sh` | Unix shell，Windows 需替代方案 | 🟡 中 |

---

## 3. 需要修改的代码文件

### 3.1 Rust 代码文件

#### 3.1.1 `src/build.rs` ⚠️ **必须修改**

**当前问题**:
```rust
env::set_var("CXX", "g++");  // 硬编码 g++
println!("cargo:rustc-link-lib=gomp");  // GNU OpenMP
let secp256k1_lib_path = current_dir.join("secp256k1/.libs");  // Unix 路径
```

**修改方案**:
- 检测操作系统，Windows 上使用 MSVC 或 MinGW
- Windows 上链接 `vcomp` (MSVC OpenMP) 或 `gomp` (MinGW)
- 使用 `Path` API 处理路径，支持 Windows 路径分隔符
- 检测编译器类型并设置相应标志

**修改内容**:
```rust
use std::env;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=utils/helper.cpp");

    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap();
    let target_env = env::var("CARGO_CFG_TARGET_ENV").unwrap();
    
    let arch = env::consts::ARCH;
    let is_windows = target_os == "windows";
    let is_msvc = target_env == "msvc";
    
    // 设置 C++ 编译器
    if is_windows {
        if is_msvc {
            // MSVC 环境
            env::set_var("CXX", "cl.exe");
        } else {
            // MinGW 环境
            env::set_var("CXX", "g++.exe");
        }
    } else {
        env::set_var("CXX", "g++");
    }

    if arch == "x86_64" {
        let mut build = cc::Build::new();
        build.flag("-Wno-unused-function")
              .flag("-Wno-unused-result")
              .cpp(true)
              .file("utils/helper.cpp");

        if is_windows {
            if is_msvc {
                // MSVC 编译选项
                build.flag("/openmp")
                     .flag("/arch:AVX2");
            } else {
                // MinGW 编译选项
                build.flag("-fopenmp")
                     .flag("-mavx2");
                println!("cargo:rustc-link-lib=gomp");
            }
        } else {
            // Linux/Unix
            build.flag("-fopenmp")
                 .flag("-mavx2")
                 .flag("-no-pie");
            println!("cargo:rustc-link-lib=gomp");
        }

        build.compile("helper.a");

        // 处理 secp256k1 库路径
        let current_dir = env::current_dir().expect("error get directory");
        let secp256k1_lib_path = if is_windows {
            // Windows 上可能使用不同的构建系统
            current_dir.join("secp256k1").join("build").join("lib")
        } else {
            current_dir.join("secp256k1").join(".libs")
        };

        println!("cargo:rustc-link-lib=static=secp256k1");
        println!("cargo:rustc-link-search=native={}", secp256k1_lib_path.display());
        println!("cargo:warning=secp256k1 library path: {}", secp256k1_lib_path.display());
    } else {
        // 非 x86_64 架构
        cc::Build::new()
            .flag("-Wno-unused-function")
            .cpp(true)
            .file("utils/helper.cpp")
            .compile("helper.a");

        let current_dir = env::current_dir().expect("error get directory");
        let secp256k1_lib_path = if is_windows {
            current_dir.join("secp256k1").join("build").join("lib")
        } else {
            current_dir.join("secp256k1").join(".libs")
        };

        println!("cargo:rustc-link-lib=static=secp256k1");
        println!("cargo:rustc-link-search=native={}", secp256k1_lib_path.display());
        println!("cargo:warning=secp256k1 library path: {}", secp256k1_lib_path.display());
    }
}
```

---

### 3.2 C++ 代码文件

#### 3.2.1 `utils/helper.cpp` ⚠️ **必须修改**

**当前问题**:
```cpp
#include <sched.h>  // Linux 特定头文件
sched_getcpu()  // Linux 特定函数
```

**修改方案**:
- 使用条件编译，Windows 上移除或替换 `sched_getcpu()`
- Windows 上可以使用 `GetCurrentProcessorNumber()` (Windows API)

**修改内容**:
```cpp
// 在文件开头添加平台检测
#ifdef _WIN32
    #include <windows.h>
    #include <processthreadsapi.h>
    #define get_cpu_id() GetCurrentProcessorNumber()
#elif defined(__linux__)
    #include <sched.h>
    #define get_cpu_id() sched_getcpu()
#else
    #define get_cpu_id() 0  // 其他平台返回 0
#endif

// 修改使用 sched_getcpu() 的地方
// 原代码:
// if (!good) printf("encrypter %d is not good\n", sched_getcpu());

// 修改为:
if (!good) printf("encrypter %d is not good\n", get_cpu_id());
```

**完整修改位置**:
- 第 96 行: `#include <sched.h>` → 条件包含
- 第 165 行: `sched_getcpu()` → `get_cpu_id()`
- 第 199 行: `sched_getcpu()` → `get_cpu_id()`

---

### 3.3 Python 脚本文件

#### 3.3.1 `control.py` ⚠️ **必须修改**

**当前问题**:
```python
find_port = "lsof -t -i :8111"  # Unix 命令
subprocess.run(f"kill -9 {PID}", shell=True)  # Unix 命令
```

**修改方案**:
- 使用 `platform` 模块检测操作系统
- Windows 上使用 `netstat` 和 `taskkill`
- 或使用跨平台的 Python 库（如 `psutil`）

**修改内容**:
```python
import subprocess
import time
import sys
import platform
import os

# ... existing code ...

def find_port_pid_windows(port):
    """Windows 上查找占用端口的进程 ID"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True,
            capture_output=True,
            text=True
        )
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'LISTENING' in line:
                parts = line.split()
                if len(parts) > 0:
                    return parts[-1]
        return None
    except:
        return None

def find_port_pid_unix(port):
    """Unix/Linux 上查找占用端口的进程 ID"""
    try:
        result = subprocess.run(
            f"lsof -t -i :{port}",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except:
        return None

def kill_process(pid):
    """跨平台杀死进程"""
    if not pid:
        return
    
    if platform.system() == "Windows":
        subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False)
    else:
        subprocess.run(f"kill -9 {pid}", shell=True, check=False)

def find_port_pid(port):
    """跨平台查找端口进程 ID"""
    if platform.system() == "Windows":
        return find_port_pid_windows(port)
    else:
        return find_port_pid_unix(port)

# 修改原函数
def pirex_test(case):
    PID = find_port_pid(8111)
    if PID:
        kill_process(PID)

    for test in case:
        subprocess.run(test, shell=True, check=True)
        subprocess.run(build, shell=True, check=True)
        
        # Windows 上可执行文件需要 .exe 扩展名
        prep_cmd = prep
        if platform.system() == "Windows":
            prep_cmd = prep.replace("./target/release/", ".\\target\\release\\") + ".exe"
        
        subprocess.run(prep_cmd, shell=True, check=True)
        
        process = subprocess.Popen(pirex_server, shell=True)
        subprocess.run(pirex_client, shell=True, check=True)

        PID = find_port_pid(8111)
        if PID:
            kill_process(PID)

# 类似修改 pirexx_test 函数
```

**可执行文件路径处理**:
```python
# 在文件开头添加
if platform.system() == "Windows":
    EXE_EXT = ".exe"
    PATH_SEP = "\\"
else:
    EXE_EXT = ""
    PATH_SEP = "/"

# 修改可执行文件路径
pirex_server = f".{PATH_SEP}target{PATH_SEP}release{PATH_SEP}pirex_sread{EXE_EXT}"
pirex_client = f".{PATH_SEP}target{PATH_SEP}release{PATH_SEP}pirex_uread{EXE_EXT}"
# ... 其他可执行文件
```

---

## 4. 需要安装的编译工具和依赖

### 4.1 Rust 工具链

**必需**:
```bash
# 安装 Rust (如果未安装)
# 访问 https://rustup.rs/ 或使用:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Windows 上使用 PowerShell:
# Invoke-WebRequest https://win.rustup.rs/x86_64 -OutFile rustup-init.exe
# .\rustup-init.exe

# 安装指定版本的 Rust toolchain
rustup toolchain install nightly-2023-09-24
rustup default nightly-2023-09-24
```

---

### 4.2 C/C++ 编译器和构建工具

#### 方案 A: 使用 MSVC (推荐用于 Windows)

**安装 Visual Studio Build Tools**:
1. 下载 Visual Studio Installer: https://visualstudio.microsoft.com/downloads/
2. 安装 "Desktop development with C++" 工作负载
3. 包含组件:
   - MSVC v143 编译器工具集
   - Windows 10/11 SDK
   - C++ CMake 工具
   - C++ 核心功能

**环境变量设置**:
```powershell
# 在 PowerShell 中运行 (以管理员身份)
# 或使用 "Developer Command Prompt for VS"
```

**验证安装**:
```powershell
cl.exe
# 应该显示 Microsoft C/C++ 编译器版本信息
```

---

#### 方案 B: 使用 MinGW-w64 (替代方案)

**安装 MinGW-w64**:
1. 使用 MSYS2 (推荐):
   ```powershell
   # 下载并安装 MSYS2: https://www.msys2.org/
   # 在 MSYS2 终端中运行:
   pacman -Syu
   pacman -S mingw-w64-x86_64-gcc
   pacman -S mingw-w64-x86_64-cmake
   pacman -S mingw-w64-x86_64-openmp
   ```

2. 或使用预编译包:
   - 下载: https://www.mingw-w64.org/downloads/
   - 解压并添加到 PATH

**环境变量设置**:
```powershell
# 添加到系统 PATH:
# C:\msys64\mingw64\bin
```

**验证安装**:
```powershell
g++.exe --version
# 应该显示 GCC 版本信息
```

---

### 4.3 CMake (用于构建 secp256k1)

**安装 CMake**:
1. 下载: https://cmake.org/download/
2. 选择 Windows x64 Installer
3. 安装时选择 "Add CMake to system PATH"

**验证安装**:
```powershell
cmake --version
```

---

### 4.4 Python 3

**安装 Python**:
1. 下载: https://www.python.org/downloads/
2. 安装时勾选 "Add Python to PATH"

**验证安装**:
```powershell
python --version
# 或
python3 --version
```

---

### 4.5 secp256k1 库构建依赖

**Windows 上构建 secp256k1**:

由于原项目使用 autotools (`autogen.sh`, `configure`, `make`)，Windows 上需要改用 CMake:

**方法 1: 使用 CMake (推荐)**:
```powershell
cd secp256k1
mkdir build
cd build

# 使用 CMake 配置
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF

# 编译
cmake --build . --config Release

# 静态库将生成在: build/lib/Release/secp256k1.lib (MSVC) 或 build/lib/libsecp256k1.a (MinGW)
```

**方法 2: 使用 MSYS2/MinGW (保留 autotools)**:
```bash
# 在 MSYS2 终端中
cd secp256k1
./autogen.sh
./configure --prefix=/mingw64
make
# 库文件在 .libs/libsecp256k1.a
```

**方法 3: 使用 vcpkg (包管理器)**:
```powershell
# 安装 vcpkg
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat

# 安装 secp256k1
.\vcpkg install secp256k1:x64-windows-static

# 在 Cargo.toml 中配置 (如果使用 Rust 的 secp256k1-sys)
```

---

### 4.6 OpenMP 支持

**MSVC**:
- 包含在 Visual Studio Build Tools 中
- 链接库: `vcomp.lib` (自动链接)

**MinGW**:
- 需要安装 `libgomp`
- 在 MSYS2 中: `pacman -S mingw-w64-x86_64-openmp`

---

## 5. 构建和运行步骤

### 5.1 环境准备检查清单

- [ ] Rust toolchain (nightly-2023-09-24) 已安装
- [ ] C/C++ 编译器 (MSVC 或 MinGW) 已安装并配置
- [ ] CMake 已安装
- [ ] Python 3 已安装
- [ ] 环境变量 PATH 已正确配置

---

### 5.2 构建 secp256k1 库

**使用 CMake (MSVC)**:
```powershell
cd secp256k1
mkdir build
cd build
cmake .. -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
cmake --build . --config Release
# 库文件位置: build/lib/Release/secp256k1.lib
```

**使用 CMake (MinGW)**:
```powershell
cd secp256k1
mkdir build
cd build
cmake .. -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
cmake --build .
# 库文件位置: build/lib/libsecp256k1.a
```

---

### 5.3 修改代码文件

按照第 3 节的修改方案，依次修改:
1. `src/build.rs`
2. `utils/helper.cpp`
3. `control.py`

---

### 5.4 构建 Rust 项目

```powershell
# 配置参数 (示例)
python config.py 64 22

# 构建项目
cargo build --release

# 如果使用 MSVC，可能需要设置环境变量:
# $env:CC = "cl.exe"
# $env:CXX = "cl.exe"
```

---

### 5.5 运行测试

```powershell
# 运行 helper
.\target\release\helper.exe

# 运行测试脚本
python control.py pirex small
```

---

## 6. 潜在问题和解决方案

### 6.1 路径问题

**问题**: Windows 路径分隔符和大小写敏感性

**解决方案**:
- 使用 Rust 的 `std::path::Path` 和 `PathBuf` API
- 避免硬编码路径分隔符
- 使用 `Path::join()` 方法

---

### 6.2 链接库问题

**问题**: Windows 上静态库扩展名不同 (`.lib` vs `.a`)

**解决方案**:
- MSVC: `secp256k1.lib`
- MinGW: `libsecp256k1.a`
- 在 `build.rs` 中根据编译器类型选择

---

### 6.3 OpenMP 链接问题

**问题**: Windows 上 OpenMP 库不同

**解决方案**:
- MSVC: 自动链接 `vcomp.lib` (无需手动指定)
- MinGW: 链接 `gomp` (需要 `-fopenmp` 标志)

---

### 6.4 内存映射问题

**问题**: `memmap` crate 在 Windows 上行为可能不同

**解决方案**:
- 使用 `memmap2` crate (更活跃的维护)
- 或确保使用最新版本的 `memmap`

---

## 7. 测试验证

### 7.1 单元测试

```powershell
cargo test
```

### 7.2 功能测试

```powershell
# 小规模测试
python config.py 64 18
cargo build --release
.\target\release\helper.exe
python control.py pirex small
```

### 7.3 性能测试

按照 README.MD 中的说明运行完整测试套件。

---

## 8. 总结

### 8.1 修改文件清单

| 文件 | 修改类型 | 优先级 |
|-----|---------|--------|
| `src/build.rs` | 重构 | 🔴 高 |
| `utils/helper.cpp` | 条件编译 | 🔴 高 |
| `control.py` | 跨平台适配 | 🟡 中 |
| `secp256k1/` | 构建方式变更 | 🔴 高 |

### 8.2 安装依赖清单

1. **Rust toolchain** (nightly-2023-09-24)
2. **C/C++ 编译器** (MSVC 或 MinGW-w64)
3. **CMake** (≥ 3.16)
4. **Python 3**
5. **OpenMP 支持** (编译器自带或单独安装)

### 8.3 关键注意事项

1. **编译器选择**: MSVC 和 MinGW 都需要不同的配置，建议统一使用一种
2. **路径处理**: 始终使用 Rust 的 `Path` API，避免硬编码路径
3. **库文件位置**: secp256k1 库的路径需要根据构建方式调整
4. **测试环境**: 建议先在小型测试用例上验证，再运行完整测试

---

## 9. 参考资源

- [Rust 跨平台开发指南](https://doc.rust-lang.org/book/ch03-05-control-flow.html)
- [cc-rs crate 文档](https://docs.rs/cc/latest/cc/)
- [secp256k1 CMake 构建](https://github.com/bitcoin-core/secp256k1)
- [Windows OpenMP 支持](https://learn.microsoft.com/en-us/cpp/parallel/openmp/openmp-in-visual-cpp)
- [MinGW-w64 文档](https://www.mingw-w64.org/)

---

**文档版本**: 1.0  
**最后更新**: 2025-01-XX  
**维护者**: [您的名字]

