$ErrorActionPreference = 'Stop'
if (-not $env:DJANGO_SECRET_KEY) { throw 'Set DJANGO_SECRET_KEY before running staging checks.' }
$env:DJANGO_SETTINGS_MODULE = 'config.settings.production'

python manage.py migrate --check
python manage.py check --deploy
python manage.py spectacular --file (Join-Path $env:TEMP 'nairobi-hospice-openapi-staging.yml') --validate
python -m pytest
Write-Output 'Staging application checks passed. Continue with browser smoke tests and restore drill.'
