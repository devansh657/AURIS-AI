function New-AurisChoiceGrammar {
    param([string[]]$Phrases, [System.Globalization.CultureInfo]$Culture)
    $choices = [System.Speech.Recognition.Choices]::new()
    $choices.Add($Phrases)
    $builder = [System.Speech.Recognition.GrammarBuilder]::new($choices)
    $builder.Culture = $Culture
    return [System.Speech.Recognition.Grammar]::new($builder)
}

function Get-AurisVoiceGrammarSet {
    param([string]$Mode, [System.Globalization.CultureInfo]$Culture)
    $commandPhrases = @(
        "open Notepad", "open Spotify", "open Microsoft Edge", "open Google Chrome",
        "open File Explorer", "open Settings", "close Notepad", "close Spotify",
        "focus Notepad", "focus Spotify", "switch to Notepad", "switch to Spotify",
        "play media", "pause media", "next track", "previous track",
        "mute volume", "unmute volume", "volume up", "volume down"
    )
    if ($Mode -eq "command") {
        $hint = New-AurisChoiceGrammar -Culture $Culture -Phrases $commandPhrases
        $hint.Name = "auris_command_hint"
        $dictation = [System.Speech.Recognition.DictationGrammar]::new()
        $dictation.Name = "auris_dictation"
        return @{ Grammars = @($hint, $dictation); Expected = @($hint.Name, $dictation.Name); Confidence = 0.45; AudioLevel = 3; EndSilenceMs = 550; AmbiguousSilenceMs = 900 }
    }
    $background = [System.Speech.Recognition.DictationGrammar]::new()
    $background.Name = "background_speech_$Mode"
    if ($Mode -eq "wake") {
        $phrases = @("AURIS", "Hey AURIS", "Okay AURIS", "OK AURIS")
        $keyword = New-AurisChoiceGrammar -Culture $Culture -Phrases $phrases
        $keyword.Name = "auris_wake"
        $builder = [System.Speech.Recognition.GrammarBuilder]::new([System.Speech.Recognition.Choices]::new([string[]]$phrases))
        $builder.Culture = $Culture
        $builder.AppendDictation()
        $continuous = [System.Speech.Recognition.Grammar]::new($builder)
        $continuous.Name = "auris_wake_command"
        $hintBuilder = [System.Speech.Recognition.GrammarBuilder]::new([System.Speech.Recognition.Choices]::new([string[]]$phrases))
        $hintBuilder.Culture = $Culture
        $hintBuilder.Append([System.Speech.Recognition.GrammarBuilder]::new([System.Speech.Recognition.Choices]::new([string[]]$commandPhrases)))
        $hint = [System.Speech.Recognition.Grammar]::new($hintBuilder)
        $hint.Name = "auris_wake_command_hint"
        return @{ Grammars = @($keyword, $continuous, $hint, $background); Expected = @($keyword.Name, $continuous.Name, $hint.Name); Confidence = 0.62; AudioLevel = 5; EndSilenceMs = 400; AmbiguousSilenceMs = 700 }
    }
    if ($Mode -eq "interrupt") {
        $interrupt = New-AurisChoiceGrammar -Culture $Culture -Phrases @(
            "stop", "AURIS stop", "pause", "cancel", "cancel that", "be quiet",
            "cancel response", "do not send it", "take no further action",
            "let me take over", "continue", "change the plan", "repeat that",
            "explain what you're doing"
        )
        $interrupt.Name = "auris_interrupt"
        return @{ Grammars = @($interrupt, $background); Expected = @($interrupt.Name); Confidence = 0.62; AudioLevel = 3; EndSilenceMs = 300; AmbiguousSilenceMs = 450 }
    }
    throw "The voice-input mode is unsupported."
}

function Test-AurisWakePrefix {
    param($Result)
    if ($null -eq $Result -or $Result.Text -notmatch '^(?:(?:hey|okay|ok)\s+)?auris\b') { return $false }
    $prefixWords = ($Matches[0] -split '\s+').Count
    if ($Result.Words.Count -lt $prefixWords) { return $false }
    for ($index = 0; $index -lt $prefixWords; $index++) {
        if ($Result.Words[$index].Confidence -lt 0.62) { return $false }
    }
    return $true
}
