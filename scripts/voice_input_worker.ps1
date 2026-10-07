$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-JsonLine {
    param([hashtable]$Payload)

    [Console]::Out.WriteLine(($Payload | ConvertTo-Json -Compress -Depth 5))
    [Console]::Out.Flush()
}

. (Join-Path $PSScriptRoot "voice_grammars.ps1")

$recognizer = $null
$cancelEvent = $null
$sourcePrefix = "AURIS-VOICE-INPUT-$PID"
$eventSources = @(
    "$sourcePrefix-HYPOTHESIZED",
    "$sourcePrefix-RECOGNIZED",
    "$sourcePrefix-REJECTED",
    "$sourcePrefix-COMPLETED",
    "$sourcePrefix-AUDIOLEVEL"
)

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

    $recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::new($selected.Culture)
    $grammarSets = @{}
    foreach ($grammarMode in @("wake", "command", "interrupt")) {
        $grammarSets[$grammarMode] = Get-AurisVoiceGrammarSet -Mode $grammarMode -Culture $selected.Culture
        foreach ($grammar in $grammarSets[$grammarMode].Grammars) {
            $grammar.Enabled = $false
            $recognizer.LoadGrammar($grammar)
        }
    }
    $cancelName = "Local\AURISVoiceInputCancel-$PID-$([Guid]::NewGuid().ToString())"
    $cancelEvent = [Threading.EventWaitHandle]::new($false, [Threading.EventResetMode]::AutoReset, $cancelName)
    $recognizer.InitialSilenceTimeout = [TimeSpan]::FromSeconds(20)
    $recognizer.BabbleTimeout = [TimeSpan]::FromSeconds(20)
    $recognizer.EndSilenceTimeout = [TimeSpan]::FromMilliseconds(550)
    $recognizer.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromMilliseconds(900)
    Register-ObjectEvent -InputObject $recognizer -EventName SpeechHypothesized -SourceIdentifier $eventSources[0] | Out-Null
    Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognized -SourceIdentifier $eventSources[1] | Out-Null
    Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognitionRejected -SourceIdentifier $eventSources[2] | Out-Null
    Register-ObjectEvent -InputObject $recognizer -EventName RecognizeCompleted -SourceIdentifier $eventSources[3] | Out-Null
    Register-ObjectEvent -InputObject $recognizer -EventName AudioLevelUpdated -SourceIdentifier $eventSources[4] | Out-Null

    Write-JsonLine @{
        type = "ready"
        provider = "windows_system_speech_stream"
        language = $selected.Culture.Name
        recognizer_id = $selected.Id
        recognizer = $selected.Description
        pid = $PID
        audio_storage = $false
        wake_strategy = "prefix_command_with_background_competitor"
        wake_acknowledgement = "silent"
        accepts_continuous_commands = $true
        cancel_event = $cancelName
    }

    while ($true) {
        $line = [Console]::In.ReadLine()
        if ($null -eq $line) {
            break
        }
        $request = $null
        try {
            $request = $line | ConvertFrom-Json
            if ($request.operation -eq "shutdown") {
                break
            }
            $propertyNames = @($request.PSObject.Properties.Name | Sort-Object)
            if (($propertyNames -join ",") -ne "mode,operation,request_id,timeout_seconds") {
                throw "The voice-input request schema is invalid."
            }
            if ($request.operation -ne "listen") {
                throw "The voice-input operation is unsupported."
            }
            $requestId = ([Guid]::Parse([string]$request.request_id)).ToString()
            $mode = [string]$request.mode
            if ($mode -notin @("command", "wake", "interrupt")) {
                throw "The voice-input mode is unsupported."
            }
            $timeoutSeconds = [Math]::Max(2, [Math]::Min(30, [int]$request.timeout_seconds))

            Get-Event -ErrorAction SilentlyContinue | Remove-Event -ErrorAction SilentlyContinue
            foreach ($grammarMode in $grammarSets.Keys) {
                foreach ($grammar in $grammarSets[$grammarMode].Grammars) { $grammar.Enabled = $grammarMode -eq $mode }
            }
            $grammarSet = $grammarSets[$mode]
            $minimumConfidence = $grammarSet.Confidence
            $minimumAudioLevel = $grammarSet.AudioLevel
            $recognizer.EndSilenceTimeout = [TimeSpan]::FromMilliseconds($grammarSet.EndSilenceMs)
            $recognizer.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromMilliseconds($grammarSet.AmbiguousSilenceMs)
            if ($mode -ne "wake") { $cancelEvent.Reset() | Out-Null }

            $started = [Diagnostics.Stopwatch]::StartNew()
            $recognized = $null
            $rejected = $null
            $completionError = $null
            $completed = $false
            $cancelledForTimeout = $false
            $cancelledForPriority = $false
            $currentAudioLevel = 0
            $peakAudioLevel = 0
            $lastLevelReport = [DateTime]::MinValue
            $deadline = [DateTime]::UtcNow.AddSeconds($timeoutSeconds)
            $recognizer.SetInputToDefaultAudioDevice()
            $recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Single)

            while (-not $completed) {
                foreach ($event in @(Get-Event -ErrorAction SilentlyContinue)) {
                    try {
                        if ($event.SourceIdentifier -eq $eventSources[0]) {
                            $hypothesis = $event.SourceEventArgs.Result
                            $hypothesisGrammar = if ($null -ne $hypothesis -and $null -ne $hypothesis.Grammar) { [string]$hypothesis.Grammar.Name } else { "" }
                            $publishPartial = $mode -eq "command" -or $hypothesisGrammar -in @("auris_wake", "auris_interrupt")
                            if ($publishPartial -and $null -ne $hypothesis -and -not [string]::IsNullOrWhiteSpace($hypothesis.Text)) {
                                Write-JsonLine @{
                                    type = "partial"
                                    request_id = $requestId
                                    text = ([string]$hypothesis.Text).Substring(0, [Math]::Min(500, ([string]$hypothesis.Text).Length))
                                    confidence = [Math]::Round($hypothesis.Confidence, 3)
                                    language = $selected.Culture.Name
                                }
                            }
                        } elseif ($event.SourceIdentifier -eq $eventSources[1]) {
                            $recognized = $event.SourceEventArgs.Result
                        } elseif ($event.SourceIdentifier -eq $eventSources[2]) {
                            $rejected = $event.SourceEventArgs.Result
                        } elseif ($event.SourceIdentifier -eq $eventSources[3]) {
                            $completionError = $event.SourceEventArgs.Error
                            $completed = $true
                        } elseif ($event.SourceIdentifier -eq $eventSources[4]) {
                            $currentAudioLevel = [Math]::Max(0, [Math]::Min(100, [int]$event.SourceEventArgs.AudioLevel))
                            $peakAudioLevel = [Math]::Max($peakAudioLevel, $currentAudioLevel)
                            if (([DateTime]::UtcNow - $lastLevelReport).TotalMilliseconds -ge 200) {
                                Write-JsonLine @{
                                    type = "audio_level"
                                    request_id = $requestId
                                    level = $currentAudioLevel
                                    peak = $peakAudioLevel
                                }
                                $lastLevelReport = [DateTime]::UtcNow
                            }
                        }
                    } finally {
                        Remove-Event -EventIdentifier $event.EventIdentifier -ErrorAction SilentlyContinue
                    }
                }
                if ($mode -eq "wake" -and -not $completed -and -not $cancelledForPriority -and $cancelEvent.WaitOne(0)) {
                    $cancelledForPriority = $true
                    $recognizer.RecognizeAsyncCancel()
                    $deadline = [DateTime]::UtcNow.AddSeconds(2)
                } elseif (-not $completed -and ($cancelledForTimeout -or $cancelledForPriority) -and [DateTime]::UtcNow -ge $deadline) {
                    throw "The recognizer did not finish cancellation in time."
                } elseif (-not $completed -and -not $cancelledForTimeout -and [DateTime]::UtcNow -ge $deadline) {
                    $cancelledForTimeout = $true
                    $recognizer.RecognizeAsyncCancel()
                    $deadline = [DateTime]::UtcNow.AddSeconds(2)
                }
                if (-not $completed) {
                    Start-Sleep -Milliseconds 35
                }
            }
            $started.Stop()
            $recognizer.SetInputToNull()

            if ($cancelledForPriority) {
                Write-JsonLine @{ type = "result"; request_id = $requestId; ok = $false; preempted = $true; audio_stored = $false }
                continue
            }

            if ($null -ne $completionError) {
                throw $completionError
            }
            if ($null -eq $recognized) {
                $confidence = if ($null -ne $rejected) { [Math]::Round($rejected.Confidence, 3) } else { $null }
                Write-JsonLine @{
                    type = "result"
                    request_id = $requestId
                    ok = $false
                    error = if ($cancelledForTimeout) { "The listening window closed without a clear utterance." } else { "No clear utterance was recognized." }
                    confidence = $confidence
                    language = $selected.Culture.Name
                    recognition_ms = $started.ElapsedMilliseconds
                    audio_stored = $false
                    peak_audio_level = $peakAudioLevel
                    audio_signal_detected = $peakAudioLevel -ge 2
                    tentative_text = [string]$recognized.Text
                }
                continue
            }

            $confidence = [Math]::Round($recognized.Confidence, 3)
            $grammarName = if ($null -ne $recognized.Grammar) { [string]$recognized.Grammar.Name } else { "" }
            if ($grammarName -notin $grammarSet.Expected -or ($mode -eq "wake" -and -not (Test-AurisWakePrefix -Result $recognized))) {
                Write-JsonLine @{
                    type = "result"
                    request_id = $requestId
                    ok = $false
                    error = if ($mode -eq "wake") { "Wake word not heard." } else { "No interruption phrase was heard." }
                    confidence = $confidence
                    language = $selected.Culture.Name
                    recognition_ms = $started.ElapsedMilliseconds
                    audio_stored = $false
                    peak_audio_level = $peakAudioLevel
                    audio_signal_detected = $peakAudioLevel -ge 2
                    background_speech_detected = $true
                    matched_grammar = $grammarName
                }
                continue
            }
            if ($mode -eq "command" -and $grammarName -eq "auris_command_hint") {
                $minimumConfidence = 0.32
            }
            if ($recognized.Confidence -lt $minimumConfidence -or $peakAudioLevel -lt $minimumAudioLevel) {
                Write-JsonLine @{
                    type = "result"
                    request_id = $requestId
                    ok = $false
                    error = "Speech was detected, but recognition confidence was too low."
                    confidence = $confidence
                    language = $selected.Culture.Name
                    recognition_ms = $started.ElapsedMilliseconds
                    audio_stored = $false
                    peak_audio_level = $peakAudioLevel
                    audio_signal_detected = $peakAudioLevel -ge 2
                    matched_grammar = $grammarName
                }
                continue
            }

            $result = @{
                type = "result"
                request_id = $requestId
                ok = $true
                confidence = $confidence
                language = $selected.Culture.Name
                recognition_ms = $started.ElapsedMilliseconds
                audio_stored = $false
                peak_audio_level = $peakAudioLevel
                audio_signal_detected = $peakAudioLevel -ge 2
                matched_grammar = $grammarName
            }
            if ($mode -eq "wake") {
                $result.wake_word = "AURIS"
                $result.recognized_as = $recognized.Text
            } elseif ($mode -eq "interrupt") {
                $result.phrase = $recognized.Text
            } else {
                $result.text = $recognized.Text
            }
            Write-JsonLine $result
        } catch {
            if ($null -ne $recognizer) {
                try { $recognizer.SetInputToNull() } catch {}
            }
            Write-JsonLine @{
                type = "result"
                request_id = if ($null -ne $request) { [string]$request.request_id } else { "" }
                ok = $false
                error = $_.Exception.Message
                restart_required = $true
                audio_stored = $false
            }
        }
    }
} catch {
    Write-JsonLine @{
        type = "fatal"
        ok = $false
        error = $_.Exception.Message
        audio_stored = $false
    }
    exit 1
} finally {
    if ($null -ne $cancelEvent) { $cancelEvent.Dispose() }
    foreach ($source in $eventSources) {
        Unregister-Event -SourceIdentifier $source -ErrorAction SilentlyContinue
    }
    Get-Event -ErrorAction SilentlyContinue | Remove-Event -ErrorAction SilentlyContinue
    if ($null -ne $recognizer) {
        try { $recognizer.RecognizeAsyncCancel() } catch {}
        $recognizer.Dispose()
    }
}
