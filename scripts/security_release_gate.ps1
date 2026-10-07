$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$cloudPython = Join-Path $root ".cloud-venv\Scripts\python.exe"
$dotnet = Join-Path $root ".dotnet\dotnet.exe"
$node = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$androidSdk = Join-Path $root ".android-sdk"
$apk = Join-Path $root "android\app\build\outputs\apk\debug\app-debug.apk"
$apksigner = Join-Path $androidSdk "build-tools\36.0.0\apksigner.bat"
$reportPath = Join-Path $root "dist\security-release-gate.json"
$checks = [System.Collections.Generic.List[object]]::new()

function Invoke-GateCheck {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    $started = [DateTimeOffset]::UtcNow
    & $Action
    $exitCode = $LASTEXITCODE
    $checks.Add([ordered]@{
        name = $Name
        passed = $exitCode -eq 0
        exit_code = $exitCode
        duration_ms = [math]::Round(([DateTimeOffset]::UtcNow - $started).TotalMilliseconds)
    })
    if ($exitCode -ne 0) {
        throw "Security release-gate check failed: $Name"
    }
}

foreach ($required in @($python, $cloudPython, $dotnet, $node, $apksigner, $apk)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "A required release-gate dependency or artifact is missing: $required"
    }
}

Push-Location $root
try {
    Invoke-GateCheck "local_security_contracts" {
        & $python -m unittest `
            tests.test_auth `
            tests.test_application_state `
            tests.test_browser_agent `
            tests.test_capabilities `
            tests.test_database `
            tests.test_memory_service `
            tests.test_model_gateway `
            tests.test_model_council `
            tests.test_policy `
            tests.test_predictive_intelligence `
            tests.test_proactive_agent `
            tests.test_privacy `
            tests.test_research_agent `
            tests.test_repair_agent `
            tests.test_telephony_agent `
            tests.test_device_fabric `
            tests.test_interaction_agent `
            tests.test_ui_automation `
            tests.test_local_ipc `
            tests.test_windows_secrets `
            tests.test_runtime `
            tests.test_runtime_launcher `
            tests.test_screen_context `
            tests.test_system_status `
            tests.test_storage `
            tests.test_communications_agent `
            tests.test_file_agent `
            tests.test_coding_agent `
            tests.test_codex_workspace_agent `
            tests.test_project_agent `
            tests.test_device_agent `
            tests.test_decision_intelligence `
            tests.test_supervisor `
            tests.test_workflow_engine `
            tests.test_world_model `
            tests.test_work_product_agent `
            tests.test_server_repair_approval `
            tests.test_server_memory `
            tests.test_server_local_operations `
            tests.test_voice `
            tests.test_speech_text `
            tests.test_speech_input_worker `
            tests.test_voice_daemon `
            tests.test_voice_turns `
            tests.test_app_followups `
            tests.test_local_client `
            tests.test_desktop_companion
    }
    Invoke-GateCheck "cloud_command_security" {
        & $cloudPython -m unittest tests.test_cloud_command_api
    }
    Invoke-GateCheck "windows_service_security" {
        & $dotnet test ".\windows\AURIS.Windows.slnx" --configuration Release --no-restore --verbosity quiet
    }
    Invoke-GateCheck "frontend_syntax" {
        & $node --check ".\web\app.js"
        if ($LASTEXITCODE -eq 0) {
            & $node --check ".\web\neural-core.js"
        }
        if ($LASTEXITCODE -eq 0) {
            & $node --check ".\scripts\browser_worker.mjs"
        }
        if ($LASTEXITCODE -eq 0) {
            & $node --check ".\scripts\capture_cognitive_ui.mjs"
        }
        if ($LASTEXITCODE -eq 0) {
            & $node --check ".\scripts\capture_coding_ui.mjs"
        }
        if ($LASTEXITCODE -eq 0) {
            & $node --check ".\scripts\capture_voice_ui.mjs"
        }
    }
    Invoke-GateCheck "windows_speech_grammars" {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\test_voice_grammars.ps1")
    }
    Invoke-GateCheck "local_acoustic_speech" {
        & (Join-Path $root ".speech-venv\Scripts\python.exe") (Join-Path $root "scripts\accept_local_speech.py")
    }
    Invoke-GateCheck "android_apk_signature" {
        $previousJavaHome = $env:JAVA_HOME
        $env:JAVA_HOME = "C:\Program Files\Java\jdk-21"
        try {
            & $apksigner verify --verbose $apk
        }
        finally {
            $env:JAVA_HOME = $previousJavaHome
        }
    }
}
finally {
    Pop-Location
}

$windowsManifestPath = Join-Path $root "dist\windows-service\artifact-manifest.json"
$windowsManifest = if (Test-Path -LiteralPath $windowsManifestPath) {
    Get-Content -LiteralPath $windowsManifestPath -Raw | ConvertFrom-Json
} else {
    $null
}
$blockers = @(
    "Trusted Authenticode certificate and signed Windows service installation are absent.",
    "Production cloud account, domain, secret vault, PostgreSQL, trusted TLS/mTLS ingress, and identity provider are absent.",
    "Production telephony provider onboarding, purchased number, trusted WSS ingress, consent review, transfer testing, and acoustic acceptance are absent.",
    "Android release signing, physical-device installation, and secure cloud enrolment are absent.",
    "Independent penetration testing and real multi-device recovery exercises have not been completed."
)
$report = [ordered]@{
    product = "AURIS"
    evaluation = "passed"
    production_ready = $false
    generated_at = [DateTimeOffset]::UtcNow.ToString("o")
    checks = @($checks)
    artifacts = [ordered]@{
        android_debug_apk_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $apk).Hash
        windows_service_sha256 = $windowsManifest.sha256
        windows_service_authenticode = $windowsManifest.authenticode_status
    }
    blockers = $blockers
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8
Write-Output "AURIS security release-gate evaluation passed."
Write-Output "Production ready: False"
Write-Output "Report: $reportPath"
