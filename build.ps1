# PowerShell build script
# Automatically set MinGW environment and build the project

# Set MinGW path
$mingw_path = "D:\Applications\tools\QT\Tools\mingw1120_64\bin"

# Check if MinGW exists
if (-not (Test-Path "$mingw_path\g++.exe")) {
    Write-Host "Error: MinGW compiler not found" -ForegroundColor Red
    Write-Host "Please check path: $mingw_path" -ForegroundColor Yellow
    exit 1
}

# Add to PATH
$env:PATH = "$mingw_path;$env:PATH"

Write-Host "MinGW environment set" -ForegroundColor Green
Write-Host "MinGW path: $mingw_path" -ForegroundColor Cyan

# Verify compiler
Write-Host "`nVerifying compiler..." -ForegroundColor Yellow
g++ --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: g++ is not available" -ForegroundColor Red
    exit 1
}

# Build project
Write-Host "`nStarting build..." -ForegroundColor Yellow
cargo build --release

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBuild successful!" -ForegroundColor Green
} else {
    Write-Host "`nBuild failed!" -ForegroundColor Red
    exit 1
}
