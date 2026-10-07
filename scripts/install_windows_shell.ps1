param(
    [switch]$SkipStartup
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$powershellPath = (Get-Command powershell.exe).Source
$desktop = [Environment]::GetFolderPath("Desktop")
$startup = [Environment]::GetFolderPath("Startup")
$shell = New-Object -ComObject WScript.Shell

function New-AurisShortcut {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Script,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $powershellPath
    $shortcut.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Script`""
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = $Description
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
    $shortcut.Save()
}

$desktopShortcut = Join-Path $desktop "AURIS One.lnk"
$desktopShortcutArguments = @{
    Path = $desktopShortcut
    Script = (Join-Path $PSScriptRoot "launch_auris.ps1")
    Description = "Open the authenticated AURIS personal intelligence system"
}
New-AurisShortcut @desktopShortcutArguments

$startupShortcut = $null
if (-not $SkipStartup) {
    $startupShortcut = Join-Path $startup "AURIS One Background.lnk"
    $startupShortcutArguments = @{
        Path = $startupShortcut
        Script = (Join-Path $PSScriptRoot "start_auris.ps1")
        Description = "Start the AURIS portal, voice core, tray agent, and global controls at Windows sign-in"
    }
    New-AurisShortcut @startupShortcutArguments
}

@{
    ok = $true
    desktop_shortcut = $desktopShortcut
    startup_shortcut = $startupShortcut
    standard_user = -not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} | ConvertTo-Json -Compress
