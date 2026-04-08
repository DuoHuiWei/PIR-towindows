param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath
)

$lines = Get-Content -LiteralPath $ConfigPath -Encoding UTF8
$currentSection = ""

foreach ($rawLine in $lines) {
    $line = $rawLine.Trim()

    if (-not $line) { continue }
    if ($line.StartsWith("#")) { continue }

    if ($line.StartsWith("[") -and $line.EndsWith("]")) {
        $currentSection = $line.TrimStart("[").TrimEnd("]")
        continue
    }

    $parts = $line -split "=", 2
    if ($parts.Count -ne 2) { continue }

    $key = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"')

    if ($currentSection) {
        Write-Output "set $key=$value"
    }
}
