param(
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvRoot = Join-Path $projectRoot ".voice-gpu-venv"
$voicePython = Join-Path $venvRoot "Scripts\python.exe"
$modelRoot = Join-Path $projectRoot "data\voice\kokoro"

if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    throw "AURIS Kokoro CUDA requires a supported NVIDIA GPU and driver."
}

if (-not (Test-Path -LiteralPath $voicePython)) {
    & $PythonPath -m venv $venvRoot
}

& $voicePython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot "requirements-voice-gpu.txt")
if ($LASTEXITCODE -ne 0) {
    throw "The AURIS Kokoro CUDA dependencies could not be installed."
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

$assetRoot = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
Install-VerifiedAsset `
    -Uri "$assetRoot/kokoro-v1.0.fp16.onnx" `
    -Path (Join-Path $modelRoot "kokoro-v1.0.fp16.onnx") `
    -Sha256 "C1610A859F3BDEA01107E73E50100685AF38FFF88F5CD8E5C56DF109EC880204"
Install-VerifiedAsset `
    -Uri "$assetRoot/voices-v1.0.bin" `
    -Path (Join-Path $modelRoot "voices-v1.0.bin") `
    -Sha256 "BCA610B8308E8D99F32E6FE4197E7EC01679264EFED0CAC9140FE9C29F1FBF7D"

& $voicePython (Join-Path $projectRoot "scripts\benchmark_kokoro_gpu.py")
if ($LASTEXITCODE -ne 0) {
    throw "The AURIS Kokoro CUDA runtime failed its synthesis benchmark."
}
