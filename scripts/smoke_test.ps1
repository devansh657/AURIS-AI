param(
    [int]$Port = 8765
)

$baseUrl = "http://127.0.0.1:$Port"
$tokenPath = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")) "data\portal.token"
$token = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
[void](Invoke-WebRequest -Uri "$baseUrl/?access_token=$([Uri]::EscapeDataString($token))" -WebSession $session -UseBasicParsing -TimeoutSec 5)
$sessionInfo = Invoke-RestMethod -Uri "$baseUrl/api/session" -WebSession $session -TimeoutSec 5
$headers = @{ "X-AURIS-CSRF" = $sessionInfo.session.csrf_token }
$status = Invoke-RestMethod -Uri "$baseUrl/api/status" -WebSession $session -TimeoutSec 5
$voice = Invoke-RestMethod -Uri "$baseUrl/api/voice/status" -WebSession $session -TimeoutSec 5
$device = Invoke-RestMethod -Uri "$baseUrl/api/device/capabilities" -WebSession $session -TimeoutSec 5
$body = @{ command = "AURIS, show laptop health and active tasks"; project_id = "auris-one"; mode = "command" } | ConvertTo-Json
$command = Invoke-RestMethod -Uri "$baseUrl/api/command" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 15

if (-not $status.ok -or -not $voice.ok -or -not $device.ok -or -not $command.ok -or $command.plan.state -ne "completed") {
    throw "AURIS smoke test failed."
}

Write-Output "AURIS smoke test passed."
Write-Output "Device: $($status.status.device.machine)"
Write-Output "Voice: $($voice.voice.input) -> $($voice.voice.voice)"
Write-Output "Device capabilities: $($device.capabilities.Count)"
Write-Output "Task: $($command.plan.task_id)"
