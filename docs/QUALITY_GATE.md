# Quality Gate

Every pull request must pass compilation, Ruff, Django checks, and the complete pytest suite. Changes affecting authorization, clinical records, documents, authentication, or financial workflows must include a regression test.

Production releases additionally require:

- `python manage.py check --deploy` with production environment variables;
- a successful database migration check;
- a backup created by `scripts/backup.ps1`;
- a restore drill against an isolated target;
- staging smoke tests from `scripts/staging_smoke.ps1`;
- verification that private media is not served as public static/media content.
