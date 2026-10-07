param(
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvRoot = Join-Path $projectRoot ".voice-venv"
$voicePython = Join-Path $venvRoot "Scripts\python.exe"
$modelRoot = Join-Path $projectRoot "data\voice\piper"

if (-not (Test-Path -LiteralPath $voicePython)) {
    & $PythonPath -m venv $venvRoot
}

& $voicePython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot "requirements-voice.txt")
if ($LASTEXITCODE -ne 0) {
    throw "The AURIS voice dependencies could not be installed."
}

New-Item -ItemType Directory -Path $modelRoot -Force | Out-Null

function Install-VerifiedAsset {
    param(
        [string]$Uri,
        [string]$Path,
        [string]$Sha256
    )

    if (Test-Path -LiteralPath $Path) {
        $existingHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
        if ($existingHash -ne $Sha256) {
            throw "An existing AURIS voice asset failed integrity verification: $Path"
        }
        return
    }

    $temporaryPath = "$Path.download"
    try {
        Invoke-WebRequest -Uri $Uri -OutFile $temporaryPath -UseBasicParsing
        $downloadHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $temporaryPath).Hash
        if ($downloadHash -ne $Sha256) {
            throw "A downloaded AURIS voice asset failed integrity verification."
        }
        Move-Item -LiteralPath $temporaryPath -Destination $Path
    }
    finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}

$modelName = "en_GB-northern_english_male-medium.onnx"
$modelPath = Join-Path $modelRoot $modelName
$configPath = "$modelPath.json"
$assetRoot = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/northern_english_male/medium"

Install-VerifiedAsset `
    -Uri "$assetRoot/$modelName?download=true" `
    -Path $modelPath `
    -Sha256 "57A219AE8E638873DB7D18893304BE5069C42868F392BB95C3FF17F0690D0689"
Install-VerifiedAsset `
    -Uri "$assetRoot/$modelName.json?download=true" `
    -Path $configPath `
    -Sha256 "69557ED3D974463453E9B0C09DD99A7ED0E52B8B87B64B357DBEEB2540A97D47"

& $voicePython -c "from piper.voice import PiperVoice; import onnxruntime as ort; print('AURIS voice ready:', ort.get_version_string(), ort.get_available_providers())"
if ($LASTEXITCODE -ne 0) {
    throw "The AURIS voice runtime failed its import check."
}
