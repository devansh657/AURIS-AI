param(
    [int]$TimeoutSeconds = 8
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

try {
    Add-Type -AssemblyName System.Speech
    $installed = @([System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers())
    $selected = $installed | Where-Object { $_.Culture.Name -eq "en-GB" } | Select-Object -First 1
    if (-not $selected) {
        $selected = $installed | Where-Object { $_.Culture.Name -eq "en-US" } | Select-Object -First 1
    }
    if (-not $selected) {
        throw "No English Windows speech recognizer is installed."
    }

    $recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::new($selected.Id)
    try {
        $recognizer.SetInputToDefaultAudioDevice()
        $recognizer.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new())
        $result = $recognizer.Recognize([TimeSpan]::FromSeconds($TimeoutSeconds))
        if ($null -eq $result) {
            @{ ok = $false; error = "I did not hear a clear command before the listening window closed."; language = $selected.Culture.Name } | ConvertTo-Json -Compress
        } elseif ($result.Confidence -lt 0.35) {
            @{ ok = $false; error = "I heard speech, but the recognition confidence was too low."; confidence = [Math]::Round($result.Confidence, 3); language = $selected.Culture.Name } | ConvertTo-Json -Compress
        } else {
            @{ ok = $true; text = $result.Text; confidence = [Math]::Round($result.Confidence, 3); language = $selected.Culture.Name } | ConvertTo-Json -Compress
        }
    } finally {
        $recognizer.Dispose()
    }
} catch {
    @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 1
}
