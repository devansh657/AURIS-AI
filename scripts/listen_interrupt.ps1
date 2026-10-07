param(
    [int]$TimeoutSeconds = 5
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
        $choices = [System.Speech.Recognition.Choices]::new()
        $choices.Add(@("stop", "AURIS stop", "be quiet", "cancel response"))
        $builder = [System.Speech.Recognition.GrammarBuilder]::new($choices)
        $builder.Culture = $selected.Culture
        $recognizer.LoadGrammar([System.Speech.Recognition.Grammar]::new($builder))
        $recognizer.SetInputToDefaultAudioDevice()
        $result = $recognizer.Recognize([TimeSpan]::FromSeconds([Math]::Max(2, [Math]::Min(10, $TimeoutSeconds))))
        if ($null -ne $result -and $result.Confidence -ge 0.45) {
            @{ ok = $true; phrase = $result.Text; confidence = [Math]::Round($result.Confidence, 3); language = $selected.Culture.Name } | ConvertTo-Json -Compress
        } else {
            @{ ok = $false; error = "No interruption heard."; language = $selected.Culture.Name } | ConvertTo-Json -Compress
        }
    } finally {
        $recognizer.Dispose()
    }
} catch {
    @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 1
}
