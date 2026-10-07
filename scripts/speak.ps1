param(
    [Parameter(Mandatory = $true)]
    [string]$Text,
    [int]$Rate = 0,
    [string]$VoiceName = "Microsoft David Desktop - English (United States)"
)

$ErrorActionPreference = "Stop"
$speaker = New-Object -ComObject SAPI.SpVoice
$speaker.Rate = [Math]::Max(-4, [Math]::Min(4, $Rate))
$speaker.Volume = 100
$selectedVoice = $speaker.GetVoices() | Where-Object { $_.GetDescription() -eq $VoiceName } | Select-Object -First 1
if (-not $selectedVoice) {
    throw "The configured AURIS fallback voice is not installed."
}
$speaker.Voice = $selectedVoice
[void]$speaker.Speak($Text)
