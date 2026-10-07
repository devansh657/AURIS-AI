param(
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dotnet = Join-Path $root ".dotnet\dotnet.exe"
$project = Join-Path $root "windows\Auris.DeviceService\Auris.DeviceService.csproj"
$output = Join-Path $root "dist\windows-service"
$manifestPath = Join-Path $output "artifact-manifest.json"

if (-not (Test-Path -LiteralPath $dotnet)) {
    throw "The pinned .NET SDK is missing. Install SDK 10.0.302 under .dotnet first."
}

$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
& $dotnet publish $project `
    --configuration $Configuration `
    --runtime win-x64 `
    --self-contained true `
    --no-restore `
    --output $output
if ($LASTEXITCODE -ne 0) {
    throw "The AURIS Windows service publish failed."
}

$executable = Join-Path $output "AURIS.DeviceService.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "The published AURIS service executable was not produced."
}
$signature = Get-AuthenticodeSignature -FilePath $executable
$manifest = [ordered]@{
    product = "AURIS Device Service"
    version = "0.1.0"
    target = "net10.0-windows/win-x64"
    self_contained = $true
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $executable).Hash
    authenticode_status = $signature.Status.ToString()
    production_install_allowed = $signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid
    built_at = [DateTimeOffset]::UtcNow.ToString("o")
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding utf8

Write-Output "AURIS Device Service published to $output"
Write-Output "Authenticode: $($manifest.authenticode_status)"
Write-Output "Production install allowed: $($manifest.production_install_allowed)"
