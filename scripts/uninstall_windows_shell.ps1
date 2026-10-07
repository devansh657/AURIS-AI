$ErrorActionPreference = "Stop"
$desktop = [Environment]::GetFolderPath("Desktop")
$startup = [Environment]::GetFolderPath("Startup")
$targets = @(
    (Join-Path $desktop "AURIS One.lnk"),
    (Join-Path $startup "AURIS One Background.lnk")
)

foreach ($target in $targets) {
    $parent = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($target))
    if ($parent -notin @([System.IO.Path]::GetFullPath($desktop), [System.IO.Path]::GetFullPath($startup))) {
        throw "Refusing to remove a shortcut outside the approved Desktop or Startup folders."
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Force
    }
}

Write-Output "AURIS per-user Windows shortcuts removed."
