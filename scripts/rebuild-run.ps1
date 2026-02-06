param(
    [switch]$NoRun
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

Write-Host "[1/4] Stopping running gh-repos-gui.exe ..."
Get-Process | Where-Object {
    $_.Path -like "*$($root.Replace('\\','\\'))*dist*gh-repos-gui.exe" -or $_.ProcessName -eq 'gh-repos-gui'
} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "[2/4] Compiling python sources ..."
python -m compileall src | Out-Null

Write-Host "[3/4] Building exe via PyInstaller ..."
pyinstaller --noconfirm --clean --onefile --windowed --name gh-repos-gui --paths src gui.py

if ($NoRun) {
    Write-Host "[4/4] Skip run (NoRun enabled)."
    exit 0
}

$exe = Join-Path $root "dist\gh-repos-gui.exe"
if (-not (Test-Path $exe)) {
    throw "Build succeeded but exe not found: $exe"
}

Write-Host "[4/4] Launching app ..."
Start-Process -FilePath $exe | Out-Null
Write-Host "Done."

