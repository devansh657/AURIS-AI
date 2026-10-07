param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "Stop"
$runtimeRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\data\voice\runtime")).Path
$audioPath = (Resolve-Path -LiteralPath $Path).Path
$prefix = $runtimeRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $audioPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "AURIS voice playback is restricted to its temporary runtime directory."
}
if ([IO.Path]::GetExtension($audioPath) -ne ".wav") {
    throw "AURIS voice playback accepts PCM WAV files only."
}

$player = New-Object System.Media.SoundPlayer $audioPath
$player.Load()
$player.PlaySync()
