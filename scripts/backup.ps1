param(
    [string]$OutputDirectory = (Join-Path (Get-Location) 'backups'),
    [string]$PrivateMediaDirectory = (Join-Path (Get-Location) 'private_media')
)

$ErrorActionPreference = 'Stop'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDirectory = Join-Path $OutputDirectory $timestamp
New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null

$engine = $env:DB_ENGINE
if ($engine -eq 'postgresql') {
    if (-not $env:DB_NAME) { throw 'DB_NAME is required for PostgreSQL backups.' }
    pg_dump --format=custom --file (Join-Path $backupDirectory 'database.dump') `
        --host ($env:DB_HOST ?? 'localhost') --port ($env:DB_PORT ?? '5432') `
        --username ($env:DB_USER ?? '') $env:DB_NAME
} elseif ($engine -eq 'mysql') {
    if (-not $env:DB_NAME) { throw 'DB_NAME is required for MySQL backups.' }
    mysqldump --single-transaction --routines --triggers `
        --host ($env:DB_HOST ?? 'localhost') --port ($env:DB_PORT ?? '3306') `
        --user ($env:DB_USER ?? '') --result-file (Join-Path $backupDirectory 'database.sql') $env:DB_NAME
} else {
    throw 'DB_ENGINE must be postgresql or mysql for production backups.'
}

if (Test-Path -LiteralPath $PrivateMediaDirectory) {
    Compress-Archive -Path (Join-Path $PrivateMediaDirectory '*') `
        -DestinationPath (Join-Path $backupDirectory 'private_media.zip')
}

Get-ChildItem -LiteralPath $backupDirectory -File |
    Where-Object { $_.Name -ne 'SHA256SUMS.csv' } |
    Get-FileHash -Algorithm SHA256 |
    Export-Csv -NoTypeInformation -Path (Join-Path $backupDirectory 'SHA256SUMS.csv')
Write-Output "Backup written to $backupDirectory"
