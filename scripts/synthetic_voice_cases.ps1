$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$cases = @(
    @{Text="Auris open Notepad"; Mode="wake"; Accept=$true},
    @{Text="Hey Auris create a folder named Reports on my Desktop"; Mode="wake"; Accept=$true},
    @{Text="Auris open YouTube in Brave"; Mode="wake"; Accept=$true},
    @{Text="Hey Auris open Notepad"; Mode="wake"; Accept=$true},
    @{Text="Hey Auris open YouTube in Brave"; Mode="wake"; Accept=$true},
    @{Text="Open Notepad"; Mode="command"; Accept=$true},
    @{Text="Stop"; Mode="interrupt"; Accept=$true},
    @{Text="The weather is nice in the park today"; Mode="wake"; Accept=$false},
    @{Text="Iris is in the room"; Mode="wake"; Accept=$false},
    @{Text="Boris open Notepad"; Mode="wake"; Accept=$false},
    @{Text="Hey Boris open Notepad"; Mode="wake"; Accept=$false},
    @{Text="Hey Iris open Notepad"; Mode="wake"; Accept=$false},
    @{Text="No worries we can talk later"; Mode="wake"; Accept=$false}
)
$output = @()
try {
    foreach ($voice in @("Microsoft Hazel Desktop", "Microsoft David Desktop")) {
        $installed = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name.StartsWith($voice) } | Select-Object -First 1
        if (-not $installed) { continue }
        $synth.SelectVoice($installed.VoiceInfo.Name)
        foreach ($case in $cases) {
            $stream = [IO.MemoryStream]::new()
            try {
                $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
                $synth.SetOutputToAudioStream($stream, $format)
                $synth.Speak($case.Text)
                $synth.SetOutputToNull()
                $output += @{voice=$installed.VoiceInfo.Name; text=$case.Text; mode=$case.Mode; accept=$case.Accept; audio=[Convert]::ToBase64String($stream.ToArray())}
            }
            finally { $stream.Dispose() }
        }
    }
    ConvertTo-Json -InputObject $output -Depth 4 -Compress
}
finally { $synth.Dispose() }
