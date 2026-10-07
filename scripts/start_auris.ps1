param(
    [int]$Port = 8765
)

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pidPath = Join-Path $projectRoot "data\server.pid"
$voicePidPath = Join-Path $projectRoot "data\voice-daemon.pid"
$companionPidPath = Join-Path $projectRoot "data\desktop-companion.pid"
$expectedVersion = "0.8.34"

function Find-AurisModuleProcess {
    param(
        [string]$ModuleName,
        [string]$PidFile
    )

    if (Test-Path -LiteralPath $PidFile) {
        $savedPid = (Get-Content -LiteralPath $PidFile -Raw).Trim()
        if ($savedPid -match '^\d+$') {
            $savedProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$savedPid" -ErrorAction SilentlyContinue
            if ($savedProcess -and $savedProcess.CommandLine -match "(?i)(?:^|\s)-m\s+$([regex]::Escape($ModuleName))(?:\s|$)") {
                return $savedProcess
            }
        }
    }

    return Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "(?i)(?:^|\s)-m\s+$([regex]::Escape($ModuleName))(?:\s|$)" } |
        Select-Object -First 1
}

function Assert-AurisModuleProcess {
    param(
        [int]$ProcessId,
        [string]$ModuleName
    )

    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(5)
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        $candidate = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($candidate) {
            Start-Sleep -Milliseconds 500
            $survivor = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
            if ($survivor) {
                return
            }
        }
        Start-Sleep -Milliseconds 200
    }
    throw "AURIS module $ModuleName did not remain running after launch."
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Bundled Python was not found at $pythonPath"
}

if (-not $env:AURIS_MODEL_PROVIDER) {
    $env:AURIS_MODEL_PROVIDER = "ollama"
    $env:AURIS_MODEL_ENDPOINT = "http://127.0.0.1:11434"
    $env:AURIS_MODEL_NAME = "gemma3:4b"
    $env:AURIS_FAST_MODEL_NAME = "qwen2.5:1.5b"
    $env:AURIS_MODEL_KEEP_ALIVE = "2h"
    $env:AURIS_MODEL_TIMEOUT = "180"
}

if (-not $env:AURIS_FAST_MODEL_NAME) {
    $env:AURIS_FAST_MODEL_NAME = "qwen2.5:1.5b"
}

if (-not $env:AURIS_MODEL_KEEP_ALIVE) {
    $env:AURIS_MODEL_KEEP_ALIVE = "2h"
}

if (-not $env:AURIS_EMBEDDING_PROVIDER) {
    $env:AURIS_EMBEDDING_PROVIDER = "ollama"
    $env:AURIS_EMBEDDING_ENDPOINT = "http://127.0.0.1:11434"
    $env:AURIS_EMBEDDING_MODEL = "nomic-embed-text"
    $env:AURIS_EMBEDDING_TIMEOUT = "60"
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $listenerProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)" -ErrorAction SilentlyContinue
    if (-not $listenerProcess -or $listenerProcess.CommandLine -notlike "*-m auris.server*") {
        throw "Port $Port is already owned by a process that is not a verified AURIS server."
    }
    try {
        $existingHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    } catch {
        $existingHealth = $null
    }
    if (-not $existingHealth -or $existingHealth.version -ne $expectedVersion) {
        & (Join-Path $PSScriptRoot "stop_auris.ps1") -Port $Port | Out-Null
        $listener = $null
        Write-Output "Stopped an obsolete AURIS runtime before launching $expectedVersion."
    } else {
        $serverPid = $listenerProcess.ProcessId
        Write-Output "AURIS server PID $serverPid is already running; checking readiness."
    }
}

if (-not $listener) {
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $pythonPath
    $startInfo.Arguments = "-m auris.server --host 127.0.0.1 --port $Port"
    $startInfo.WorkingDirectory = $projectRoot
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $process = [System.Diagnostics.Process]::Start($startInfo)

    $process.Id | Set-Content -LiteralPath $pidPath
    $serverPid = $process.Id
    Write-Output "AURIS server PID $serverPid is warming its voice and input engines."
}

$ready = $false
$deadline = [DateTimeOffset]::UtcNow.AddSeconds(35)
while ([DateTimeOffset]::UtcNow -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($health.ok -and $health.version -eq $expectedVersion) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Milliseconds 250
    }
}
if (-not $ready) {
    throw "AURIS did not become voice-ready within 35 seconds."
}
Write-Output "AURIS is ready with PID $serverPid at http://127.0.0.1:$Port"

$voiceProcess = Find-AurisModuleProcess -ModuleName "auris.voice_daemon" -PidFile $voicePidPath

if ($voiceProcess) {
    $voiceProcess.ProcessId | Set-Content -LiteralPath $voicePidPath
    Write-Output "AURIS background voice is already running with PID $($voiceProcess.ProcessId)"
} else {
    $voiceStartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $voiceStartInfo.FileName = $pythonPath
    $voiceStartInfo.Arguments = "-m auris.voice_daemon"
    $voiceStartInfo.WorkingDirectory = $projectRoot
    $voiceStartInfo.UseShellExecute = $true
    $voiceStartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $voiceProcess = [System.Diagnostics.Process]::Start($voiceStartInfo)
    $voiceProcess.Id | Set-Content -LiteralPath $voicePidPath
    Write-Output "AURIS background voice started with PID $($voiceProcess.Id)"
}

$companionProcess = Find-AurisModuleProcess -ModuleName "auris.desktop_companion" -PidFile $companionPidPath

if ($companionProcess) {
    $companionProcess.ProcessId | Set-Content -LiteralPath $companionPidPath
    Write-Output "AURIS desktop companion is already running with PID $($companionProcess.ProcessId)"
} else {
    $companionStartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $companionStartInfo.FileName = $pythonPath
    $companionStartInfo.Arguments = "-m auris.desktop_companion"
    $companionStartInfo.WorkingDirectory = $projectRoot
    $companionStartInfo.UseShellExecute = $true
    $companionStartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $companionProcess = [System.Diagnostics.Process]::Start($companionStartInfo)
    $companionProcess.Id | Set-Content -LiteralPath $companionPidPath
    Write-Output "AURIS desktop companion started with PID $($companionProcess.Id)"
}

Assert-AurisModuleProcess -ProcessId $voiceProcess.ProcessId -ModuleName "auris.voice_daemon"
Assert-AurisModuleProcess -ProcessId $companionProcess.ProcessId -ModuleName "auris.desktop_companion"
Write-Output "AURIS process trio verified: server, background voice, and desktop companion."
