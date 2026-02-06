$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$src = Join-Path $root 'src'

if (-not (Test-Path $src)) {
    throw "src not found: $src"
}

Write-Host "Watching $src"
Write-Host "On any file change, auto rebuild + run. Press Ctrl+C to stop."

$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = $src
$fsw.Filter = '*.*'
$fsw.IncludeSubdirectories = $true
$fsw.EnableRaisingEvents = $true

$scriptPath = Join-Path $PSScriptRoot 'rebuild-run.ps1'
$global:lastRun = [datetime]::MinValue

$action = {
    $now = Get-Date
    if (($now - $global:lastRun).TotalSeconds -lt 2) {
        return
    }
    $global:lastRun = $now

    Write-Host "\n[$($now.ToString('HH:mm:ss'))] Change detected -> rebuild-run"
    try {
        powershell.exe -ExecutionPolicy Bypass -File $scriptPath
    }
    catch {
        Write-Host "Rebuild failed: $($_.Exception.Message)"
    }
}

Register-ObjectEvent $fsw Changed -Action $action | Out-Null
Register-ObjectEvent $fsw Created -Action $action | Out-Null
Register-ObjectEvent $fsw Renamed -Action $action | Out-Null
Register-ObjectEvent $fsw Deleted -Action $action | Out-Null

while ($true) {
    Start-Sleep -Seconds 1
}

