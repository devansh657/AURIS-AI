param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
    throw "The registered project root is not a directory."
}

Start-Process -FilePath "explorer.exe" -ArgumentList @("`"$resolved`"")
$deadline = [DateTimeOffset]::UtcNow.AddSeconds(8)
$confirmed = $false
while ([DateTimeOffset]::UtcNow -lt $deadline -and -not $confirmed) {
    $shell = $null
    try {
        $shell = New-Object -ComObject Shell.Application
        foreach ($window in @($shell.Windows())) {
            try {
                $location = [Uri]$window.LocationURL
                if (-not $location.IsFile) {
                    continue
                }
                $windowPath = [Uri]::UnescapeDataString($location.LocalPath).Replace('/', '\')
                $windowResolved = [IO.Path]::GetFullPath($windowPath).TrimEnd('\')
                if ([string]::Equals($windowResolved, $resolved.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
                    $confirmed = $true
                    break
                }
            }
            catch {
                continue
            }
        }
    }
    finally {
        if ($null -ne $shell) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)
        }
    }
    if (-not $confirmed) {
        Start-Sleep -Milliseconds 250
    }
}

[pscustomobject]@{
    ok = $confirmed
    path = $resolved
    observed = $confirmed
    application = "File Explorer"
} | ConvertTo-Json -Compress
