param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}

$mode = if ($OneFile) { "--onefile" } else { "--onedir" }
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    $mode `
    --name "Lab Icons Windows" `
    --add-data "icons-in;icons-in" `
    --add-data "icons-out;icons-out" `
    app.py

$AppDir = Join-Path $Root "dist\Lab Icons Windows"
foreach ($folder in @("icons-in", "icons-out")) {
    $source = Join-Path $Root $folder
    $target = Join-Path $AppDir $folder
    if (Test-Path $source) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Build ready in: $Root\dist"
