param(
    [int]$StartupTimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$executable = Join-Path $root "dist\windows-service\AURIS.DeviceService.exe"
$statusPath = Join-Path $root "data\device-service-smoke-status.json"

if (-not (Test-Path -LiteralPath $executable)) {
    throw "Build the AURIS Windows service before testing it."
}
if (Test-Path -LiteralPath $statusPath) {
    Remove-Item -LiteralPath $statusPath -Force
}

$previousStatusPath = $env:AURIS_SERVICE_STATUS_PATH
$env:AURIS_SERVICE_STATUS_PATH = $statusPath
try {
    $process = Start-Process -FilePath $executable -PassThru -WindowStyle Hidden
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline -and -not (Test-Path -LiteralPath $statusPath)) {
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-Path -LiteralPath $statusPath)) {
        throw "The AURIS Device Service did not publish its health state."
    }
    $status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    if ($status.service -ne "AURIS Device Service" -or $status.state -ne "online") {
        throw "The AURIS Device Service health state is invalid."
    }
    if ($status.remote_execution -ne "disabled_until_signed_install_and_visible_broker") {
        throw "The unsigned foreground build did not preserve the remote-execution gate."
    }
    Write-Output "AURIS Device Service foreground smoke test passed."
    Write-Output "Cloud configured: $($status.cloud_configured)"
    Write-Output "Remote execution: $($status.remote_execution)"
}
finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        $process.WaitForExit()
    }
    if ($null -eq $previousStatusPath) {
        Remove-Item Env:AURIS_SERVICE_STATUS_PATH -ErrorAction SilentlyContinue
    }
    else {
        $env:AURIS_SERVICE_STATUS_PATH = $previousStatusPath
    }
    if (Test-Path -LiteralPath $statusPath) {
        Remove-Item -LiteralPath $statusPath -Force
    }
}
