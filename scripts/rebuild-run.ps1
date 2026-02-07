param(
    [switch]$NoRun
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv not found in PATH. Please install uv first: https://docs.astral.sh/uv/"
}

Write-Host "[1/5] Stopping running gh-repos-gui.exe ..."
Get-Process | Where-Object {
    $_.Path -like "*$($root.Replace('\\','\\'))*dist*gh-repos-gui.exe" -or $_.ProcessName -eq 'gh-repos-gui'
} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "[2/5] Syncing dependencies via uv ..."
uv sync --group build

Write-Host "[3/5] Compiling python sources ..."
uv run python -m compileall src | Out-Null

Write-Host "[4/5] Building exe via PyInstaller ..."
uv run pyinstaller --noconfirm --clean --onefile --windowed --name gh-repos-gui --paths src gui.py

if ($NoRun) {
    Write-Host "[5/5] Skip run (NoRun enabled)."
    exit 0
}

$exe = Join-Path $root "dist\gh-repos-gui.exe"
if (-not (Test-Path $exe)) {
    throw "Build succeeded but exe not found: $exe"
}

Write-Host "[5/5] Launching app ..."
Start-Process -FilePath $exe | Out-Null
Write-Host "Done."
