# Windows 迁移快速检查清单

## 📋 前置条件检查

- [ ] Rust toolchain (nightly-2023-09-24) 已安装
- [ ] C/C++ 编译器已安装 (MSVC 或 MinGW)
- [ ] CMake (≥3.16) 已安装
- [ ] Python 3 已安装
- [ ] 所有工具已添加到系统 PATH

---

## 🔧 必须修改的文件

### 1. `src/build.rs` ⚠️ **必须修改**
- [ ] 添加 Windows 平台检测
- [ ] 设置正确的 C++ 编译器 (MSVC 或 MinGW)
- [ ] 修改 OpenMP 链接库 (Windows 使用 `vcomp` 或 `gomp`)
- [ ] 修改 secp256k1 库路径处理

### 2. `utils/helper.cpp` ⚠️ **必须修改**
- [ ] 移除或条件编译 `#include <sched.h>`
- [ ] 替换 `sched_getcpu()` 为跨平台函数
- [ ] 添加 Windows 平台的条件编译代码

### 3. `control.py` ⚠️ **必须修改**
- [ ] 替换 `lsof` 命令为 Windows 兼容方案
- [ ] 替换 `kill` 命令为 `taskkill`
- [ ] 修改可执行文件路径处理 (添加 `.exe` 扩展名)

---

## 🏗️ 构建步骤

### 步骤 1: 构建 secp256k1 库

**MSVC 方式**:
```powershell
cd secp256k1
mkdir build
cd build
cmake .. -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
cmake --build . --config Release
```

**MinGW 方式**:
```powershell
cd secp256k1
mkdir build
cd build
cmake .. -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
cmake --build .
```

### 步骤 2: 修改代码文件
- [ ] 按照 `Windows重构方案.md` 修改所有必需文件

### 步骤 3: 构建 Rust 项目
```powershell
python config.py 64 22
cargo build --release
```

### 步骤 4: 测试
```powershell
.\target\release\helper.exe
python control.py pirex small
```

---

## ⚠️ 常见问题

### 问题 1: 找不到 secp256k1 库
- **解决**: 检查 `build.rs` 中的库路径是否正确
- MSVC: `secp256k1/build/lib/Release/`
- MinGW: `secp256k1/build/lib/`

### 问题 2: OpenMP 链接错误
- **MSVC**: 确保安装了 Visual Studio Build Tools
- **MinGW**: 安装 `mingw-w64-x86_64-openmp` (MSYS2)

### 问题 3: 找不到编译器
- **MSVC**: 使用 "Developer Command Prompt for VS"
- **MinGW**: 确保 `g++.exe` 在 PATH 中

### 问题 4: Python 脚本执行失败
- **解决**: 确保已修改 `control.py` 中的进程管理命令

---

## 📝 验证清单

- [ ] `cargo build --release` 成功完成
- [ ] `helper.exe` 可以正常运行
- [ ] `control.py` 可以找到并杀死进程
- [ ] 小规模测试 (`python control.py pirex small`) 通过

---

## 🔗 相关文档

详细说明请参考: `Windows重构方案.md`




