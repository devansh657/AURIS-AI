$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
. (Join-Path $PSScriptRoot "voice_grammars.ps1")
$installed = @([System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers())
$selected = $installed | Where-Object { $_.Culture.Name -eq "en-GB" } | Select-Object -First 1
if (-not $selected) { $selected = $installed | Where-Object { $_.Culture.Name -eq "en-US" } | Select-Object -First 1 }
if (-not $selected) { throw "No English Windows speech recognizer is installed." }
$recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::new($selected.Culture)
$reports = [Collections.Generic.List[object]]::new()
try {
    $sets = @{}
    foreach ($mode in @("wake", "command", "interrupt")) {
        $sets[$mode] = Get-AurisVoiceGrammarSet -Mode $mode -Culture $selected.Culture
        foreach ($grammar in $sets[$mode].Grammars) {
            $grammar.Enabled = $false
            $recognizer.LoadGrammar($grammar)
        }
    }
    $cases = @(
        @{ mode = "wake"; text = "AURIS"; accepted = $true },
        @{ mode = "wake"; text = "Hey AURIS open Notepad"; accepted = $true },
        @{ mode = "wake"; text = "AURIS create a folder called Reports on Desktop"; accepted = $true },
        @{ mode = "wake"; text = "we are going to the park"; accepted = $false },
        @{ mode = "wake"; text = "Iris is in the room"; accepted = $false },
        @{ mode = "command"; text = "open Notepad"; accepted = $true },
        @{ mode = "interrupt"; text = "stop"; accepted = $true },
        @{ mode = "interrupt"; text = "the music sounds nice"; accepted = $false }
    )
    foreach ($case in $cases) {
        foreach ($mode in $sets.Keys) {
            foreach ($grammar in $sets[$mode].Grammars) { $grammar.Enabled = $mode -eq $case.mode }
        }
        $result = $recognizer.EmulateRecognize([string]$case.text)
        $matched = if ($null -ne $result -and $null -ne $result.Grammar) { $result.Grammar.Name } else { "" }
        $accepted = $matched -in $sets[$case.mode].Expected
        if ($accepted -ne $case.accepted) { throw "Unexpected grammar routing for '$($case.text)': $matched" }
        $reports.Add(@{ mode = $case.mode; text = $case.text; matched_grammar = $matched; accepted = $accepted })
    }
    $weak = [PSCustomObject]@{ Text = "AURIS open Notepad"; Words = @([PSCustomObject]@{ Confidence = 0.3 }) }
    if (Test-AurisWakePrefix -Result $weak) { throw "A weak wake prefix was accepted." }
    @{ ok = $true; recognizer = $selected.Description; input = "text_emulation_not_room_audio"; cases = @($reports); weak_prefix_rejected = $true } | ConvertTo-Json -Depth 6
} finally { $recognizer.Dispose() }
