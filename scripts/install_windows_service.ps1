param(
    [string]$ServiceName = "AURISDeviceService"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$executable = Join-Path $root "dist\windows-service\AURIS.DeviceService.exe"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Installing AURIS as a Windows Service requires an elevated administrator session."
}
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Build the AURIS Windows service before installation."
}
$signature = Get-AuthenticodeSignature -FilePath $executable
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "AURIS refuses to install an unsigned or untrusted Windows service binary. Current status: $($signature.Status)."
}
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    throw "The $ServiceName service already exists. Use the signed update procedure instead of replacing it in place."
}

& sc.exe create $ServiceName binPath= ('"' + $executable + '"') start= auto DisplayName= "AURIS Device Service"
if ($LASTEXITCODE -ne 0) {
    throw "Windows rejected the AURIS service registration."
}
& sc.exe description $ServiceName "AURIS signed device trust and outbound command service"
& sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/15000/none/0
& sc.exe start $ServiceName
if ($LASTEXITCODE -ne 0) {
    throw "AURIS was registered, but Windows could not start the service."
}
Write-Output "AURIS Device Service installed and started."
