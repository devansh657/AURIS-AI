param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$voicePidPath = Join-Path $projectRoot "data\voice-daemon.pid"
$voiceStatusPath = Join-Path $projectRoot "data\voice-daemon-status.json"
$companionPidPath = Join-Path $projectRoot "data\desktop-companion.pid"
$companionStatusPath = Join-Path $projectRoot "data\desktop-companion-status.json"

function Get-AurisModuleProcesses {
    param([string]$ModuleName)

    return @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "(?i)(?:^|\s)-m\s+$([regex]::Escape($ModuleName))(?:\s|$)" })
}

function Remove-AurisRuntimeFile {
    param([string]$Path)

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Test-Path -LiteralPath $Path)) {
            return
        }
        try {
            Remove-Item -LiteralPath $Path -Force
            return
        } catch [System.IO.IOException] {
            Start-Sleep -Milliseconds 100
        }
    }
    Remove-Item -LiteralPath $Path -Force
}

foreach ($companionProcess in Get-AurisModuleProcesses -ModuleName "auris.desktop_companion") {
    Stop-Process -Id ([int]$companionProcess.ProcessId) -Force
    Wait-Process -Id ([int]$companionProcess.ProcessId) -Timeout 3 -ErrorAction SilentlyContinue
    Write-Output "AURIS desktop companion PID $($companionProcess.ProcessId) stopped."
}
Remove-AurisRuntimeFile -Path $companionPidPath
Remove-AurisRuntimeFile -Path $companionStatusPath

foreach ($voiceProcess in Get-AurisModuleProcesses -ModuleName "auris.voice_daemon") {
    Stop-Process -Id ([int]$voiceProcess.ProcessId) -Force
    Wait-Process -Id ([int]$voiceProcess.ProcessId) -Timeout 3 -ErrorAction SilentlyContinue
    Write-Output "AURIS background voice PID $($voiceProcess.ProcessId) stopped."
}
Remove-AurisRuntimeFile -Path $voicePidPath
Remove-AurisRuntimeFile -Path $voiceStatusPath

$connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $connection) {
    Write-Output "AURIS is not running on port $Port."
    exit 0
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
if (-not $process -or $process.CommandLine -notlike "*-m auris.server*") {
    throw "Port $Port is not owned by a verified AURIS server process. Nothing was stopped."
}

Stop-Process -Id $connection.OwningProcess -Force
Write-Output "AURIS server PID $($connection.OwningProcess) stopped."
