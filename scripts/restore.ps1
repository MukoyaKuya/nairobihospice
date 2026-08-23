param(
    [Parameter(Mandatory = $true)][string]$BackupDirectory,
    [Parameter(Mandatory = $true)][string]$RestoreMediaDirectory,
    [switch]$ConfirmRestore
)

$ErrorActionPreference = 'Stop'
if (-not $ConfirmRestore) { throw 'Restore is destructive. Re-run with -ConfirmRestore against an isolated target.' }
$resolvedBackup = (Resolve-Path -LiteralPath $BackupDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path $resolvedBackup 'SHA256SUMS.csv'))) {
    throw 'Backup manifest is missing; refuse to restore an unverifiable backup.'
}

$databaseDump = Join-Path $resolvedBackup 'database.dump'
$databaseSql = Join-Path $resolvedBackup 'database.sql'
$databaseSqlite = Join-Path $resolvedBackup 'database.sqlite3'
if (Test-Path -LiteralPath $databaseDump) {
    if (-not $env:RESTORE_DATABASE) { throw 'RESTORE_DATABASE must identify the isolated PostgreSQL target.' }
    pg_restore --clean --if-exists --dbname=$env:RESTORE_DATABASE $databaseDump
} elseif (Test-Path -LiteralPath $databaseSql) {
    if (-not $env:RESTORE_DATABASE) { throw 'RESTORE_DATABASE must identify the isolated MySQL target.' }
    Get-Content -Raw -LiteralPath $databaseSql | mysql $env:RESTORE_DATABASE
} elseif (Test-Path -LiteralPath $databaseSqlite) {
    Copy-Item -LiteralPath $databaseSqlite -Destination (Join-Path (Get-Location) 'production_db.sqlite3') -Force
} else {
    throw 'No supported database backup found.'
}

$mediaArchive = Join-Path $resolvedBackup 'private_media.zip'
if (Test-Path -LiteralPath $mediaArchive) {
    New-Item -ItemType Directory -Force -Path $RestoreMediaDirectory | Out-Null
    Expand-Archive -LiteralPath $mediaArchive -DestinationPath $RestoreMediaDirectory -Force
}
Write-Output 'Restore completed. Run migrations, manage.py check, and the documented smoke tests before opening traffic.'
