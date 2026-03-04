# secp256k1 构建脚本 - 使用 64 位 MinGW
# 用途: 使用 64 位 MinGW 编译器构建 secp256k1 静态库

Write-Host "=== secp256k1 构建脚本 (64位 MinGW) ===" -ForegroundColor Cyan

# 配置
# 使用 QT MinGW 11.2.0 (64位)
$mingw64_path = "D:\Applications\tools\QT\Tools\mingw1120_64\bin"
$secp256k1_dir = "D:\WorkStation\pythoncode\experiment-reproduction\windows\pirex-main\secp256k1"
$build_dir = Join-Path $secp256k1_dir "build"

# 步骤 1: 设置环境变量
Write-Host "`n[1/6] 设置 MinGW 环境变量..." -ForegroundColor Yellow
$env:PATH = "$mingw64_path;$env:PATH"

# 步骤 2: 验证编译器
Write-Host "`n[2/6] 验证编译器..." -ForegroundColor Yellow
try {
    $gcc_machine = gcc -dumpmachine 2>&1
    $gcc_version = gcc --version 2>&1 | Select-Object -First 1
    
    Write-Host "  编译器架构: $gcc_machine" -ForegroundColor Cyan
    
    if ($gcc_machine -match "x86_64|64") {
        Write-Host "  ✓ 检测到 64 位编译器" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 警告: 这不是 64 位编译器，可能无法成功构建" -ForegroundColor Red
        Write-Host "  当前架构: $gcc_machine" -ForegroundColor Yellow
    }
    
    Write-Host "  版本信息: $gcc_version" -ForegroundColor Cyan
} catch {
    Write-Host "  ✗ 错误: 无法找到 gcc 编译器" -ForegroundColor Red
    Write-Host "  请检查路径: $mingw64_path" -ForegroundColor Yellow
    exit 1
}

# 步骤 3: 检查 secp256k1 目录
Write-Host "`n[3/6] 检查 secp256k1 目录..." -ForegroundColor Yellow
if (-not (Test-Path $secp256k1_dir)) {
    Write-Host "  ✗ 错误: secp256k1 目录不存在: $secp256k1_dir" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ secp256k1 目录存在" -ForegroundColor Green

# 步骤 4: 清理旧的构建
Write-Host "`n[4/6] 清理旧的构建目录..." -ForegroundColor Yellow
if (Test-Path $build_dir) {
    Remove-Item -Recurse -Force $build_dir
    Write-Host "  ✓ 已清理旧的构建目录" -ForegroundColor Green
}
New-Item -ItemType Directory -Path $build_dir -Force | Out-Null
Write-Host "  ✓ 创建新的构建目录" -ForegroundColor Green

# 步骤 5: 配置 CMake
Write-Host "`n[5/6] 配置 CMake..." -ForegroundColor Yellow
Push-Location $build_dir

try {
    cmake $secp256k1_dir `
        -G "MinGW Makefiles" `
        -DCMAKE_BUILD_TYPE=Release `
        -DBUILD_SHARED_LIBS=OFF `
        -DCMAKE_C_COMPILER=gcc.exe `
        -DCMAKE_CXX_COMPILER=g++.exe `
        -DSECP256K1_ENABLE_MODULE_ECDH=ON `
        -DSECP256K1_ENABLE_MODULE_EXTRAKEYS=ON `
        -DSECP256K1_ENABLE_MODULE_SCHNORRSIG=ON `
        -DSECP256K1_ENABLE_MODULE_MUSIG=ON `
        -DSECP256K1_ENABLE_MODULE_ELLSWIFT=ON `
        -DSECP256K1_BUILD_BENCHMARK=OFF `
        -DSECP256K1_BUILD_TESTS=OFF `
        -DSECP256K1_BUILD_EXHAUSTIVE_TESTS=OFF 2>&1 | Tee-Object -Variable cmake_output
    
    if ($LASTEXITCODE -ne 0) {
        throw "CMake 配置失败"
    }
    
    Write-Host "  ✓ CMake 配置成功" -ForegroundColor Green
} catch {
    Write-Host "  ✗ CMake 配置失败: $_" -ForegroundColor Red
    Pop-Location
    exit 1
}

# 步骤 6: 构建
Write-Host "`n[6/6] 构建项目..." -ForegroundColor Yellow
try {
    cmake --build . 2>&1 | Tee-Object -Variable build_output
    
    if ($LASTEXITCODE -ne 0) {
        throw "构建失败"
    }
    
    Write-Host "  ✓ 构建成功" -ForegroundColor Green
} catch {
    Write-Host "  ✗ 构建失败: $_" -ForegroundColor Red
    Pop-Location
    exit 1
}

# 验证输出
Write-Host "`n=== 构建结果 ===" -ForegroundColor Cyan
$lib_path = Join-Path $build_dir "lib\libsecp256k1.a"

if (Test-Path $lib_path) {
    $lib_info = Get-Item $lib_path
    Write-Host "  ✓ 库文件已生成" -ForegroundColor Green
    Write-Host "  位置: $lib_path" -ForegroundColor Cyan
    Write-Host "  大小: $([math]::Round($lib_info.Length / 1MB, 2)) MB" -ForegroundColor Cyan
    Write-Host "  修改时间: $($lib_info.LastWriteTime)" -ForegroundColor Cyan
    
    # 检查是否需要复制到 .libs 目录
    $target_libs_dir = Join-Path $secp256k1_dir ".libs"
    $target_lib = Join-Path $target_libs_dir "libsecp256k1.a"
    
    if (-not (Test-Path $target_libs_dir)) {
        New-Item -ItemType Directory -Path $target_libs_dir -Force | Out-Null
    }
    
    if (-not (Test-Path $target_lib) -or (Get-Item $target_lib).LastWriteTime -lt $lib_info.LastWriteTime) {
        Copy-Item $lib_path -Destination $target_lib -Force
        Write-Host "`n  ✓ 已复制库文件到: $target_lib" -ForegroundColor Green
    } else {
        Write-Host "`n  ℹ 目标位置已有更新的库文件" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ 警告: 未找到库文件" -ForegroundColor Yellow
    Write-Host "  预期位置: $lib_path" -ForegroundColor Yellow
}

Pop-Location

Write-Host "`n=== 构建完成 ===" -ForegroundColor Green



