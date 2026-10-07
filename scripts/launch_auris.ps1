param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$url = "http://127.0.0.1:$Port/"
$tokenPath = Join-Path $projectRoot "data\portal.token"
$expectedVersion = "0.8.34"

try {
    $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 2
} catch {
    $health = $null
}

if ($health -and $health.ok -and $health.version -ne $expectedVersion) {
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "stop_auris.ps1") -Port $Port | Out-Null
    $health = $null
}

# Reconcile every AURIS process even when a healthy backend already owns the port.
# This repairs a missing voice daemon or desktop companion without replacing the server.
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start_auris.ps1") -Port $Port | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "AURIS process reconciliation failed with exit code $LASTEXITCODE."
}
$health = $null
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 1
        break
    } catch {
        Start-Sleep -Milliseconds 200
    }
}

if (-not $health.ok -or $health.version -ne $expectedVersion -or -not (Test-Path -LiteralPath $tokenPath)) {
    throw "AURIS did not become ready at $url"
}

$accessToken = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
[void](Invoke-WebRequest -Uri "${url}?access_token=$([Uri]::EscapeDataString($accessToken))" -WebSession $session -UseBasicParsing -TimeoutSec 5)
$sessionInfo = Invoke-RestMethod -Uri "${url}api/session" -WebSession $session -TimeoutSec 5
$headers = @{ "X-AURIS-CSRF" = $sessionInfo.session.csrf_token }
$bootstrap = Invoke-RestMethod -Uri "${url}api/session/bootstrap" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body "{}" -TimeoutSec 5
$authenticatedUrl = "${url}?bootstrap_code=$([Uri]::EscapeDataString($bootstrap.bootstrap.code))"

$edgeCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:LOCALAPPDATA "Microsoft\Edge\Application\msedge.exe")
)
$edgePath = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $edgePath) {
    throw "Microsoft Edge was not found. Open $url in a Chromium browser."
}

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $edgePath
$startInfo.Arguments = "--app=$authenticatedUrl --start-maximized"
$startInfo.UseShellExecute = $true
[void][System.Diagnostics.Process]::Start($startInfo)

Write-Output "AURIS command centre opened at $url"
