param([string]$PythonPath = "python")

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".speech-venv\Scripts\python.exe"
$model = Join-Path $root "data\voice\whisper-tiny.en"
if (-not (Test-Path -LiteralPath $python)) {
    & $PythonPath -m venv (Join-Path $root ".speech-venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the isolated speech environment." }
}
& $python -m pip install --no-cache-dir --only-binary=:all: --disable-pip-version-check -r (Join-Path $root "requirements-speech.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install the local speech dependencies." }

New-Item -ItemType Directory -Path $model -Force | Out-Null
$revision = "0d3d19a32d3338f10357c0889762bd8d64bbdeba"
$assets = @(
    @{Name="model.bin"; Hash="1a5afae06a4db91c975c9a9d78be5cc110ee4ea022ad57d55492e4550e936b2a"; Algorithm="SHA256"},
    @{Name="config.json"; Hash="4065bb3bed375b176d5465be117d2d202e210434"; Algorithm="GitBlob"},
    @{Name="tokenizer.json"; Hash="15d7bdf9ba25718ca2504eec6a8f02bc55af0a6a"; Algorithm="GitBlob"},
    @{Name="vocabulary.txt"; Hash="ee695b8d3e3c10d488304e04468efec4ca27554a"; Algorithm="GitBlob"}
)
function Get-AssetHash([string]$Path, [string]$Algorithm) {
    if ($Algorithm -eq "SHA256") { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
    $bytes = [IO.File]::ReadAllBytes($Path)
    $header = [Text.Encoding]::ASCII.GetBytes("blob $($bytes.Length)`0")
    $sha = [Security.Cryptography.SHA1]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($header + $bytes))).Replace("-", "").ToLowerInvariant() }
    finally { $sha.Dispose() }
}
foreach ($asset in $assets) {
    $path = Join-Path $model $asset.Name
    if (Test-Path -LiteralPath $path) {
        if ((Get-AssetHash $path $asset.Algorithm) -ne $asset.Hash) { throw "An existing speech asset failed verification: $($asset.Name)" }
        continue
    }
    $temporary = "$path.download"
    try {
        Invoke-WebRequest "https://huggingface.co/Systran/faster-whisper-tiny.en/resolve/$revision/$($asset.Name)" -OutFile $temporary -UseBasicParsing
        if ((Get-AssetHash $temporary $asset.Algorithm) -ne $asset.Hash) { throw "Downloaded speech asset failed verification: $($asset.Name)" }
        Move-Item -LiteralPath $temporary -Destination $path
    }
    finally { Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue }
}
& $python -c "from faster_whisper import WhisperModel; import sounddevice, webrtcvad; WhisperModel(r'$model', device='cpu', compute_type='int8', local_files_only=True); print('AURIS local speech model ready')"
if ($LASTEXITCODE -ne 0) { throw "The local speech model failed its readiness check." }
