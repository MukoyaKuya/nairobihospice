# Backup and restore runbook

This application contains clinical, identity, audit, inventory, and financial data. Backups must cover both the database and private media.

## Required policy

- Database backup: daily full backup, with more frequent WAL/binlog or provider point-in-time recovery where available.
- Private media backup: daily incremental copy and a periodic full copy.
- Retention: define a documented retention period that meets Nairobi Hospice legal and operational requirements.
- Encryption: encrypt backups in transit and at rest.
- Access: restrict backup access to approved administrators and record access events.
- Recovery objectives: document an RPO and RTO before production approval.

Proposed starting targets for owner approval: RPO of 24 hours for full daily backups and RTO of 4 hours for a verified restore. Tighten these targets if clinical service requirements demand it.

## PostgreSQL example

```bash
pg_dump --format=custom --file=pcms-YYYY-MM-DD.dump "$DATABASE_URL"
pg_restore --clean --if-exists --dbname="$RESTORE_DATABASE_URL" pcms-YYYY-MM-DD.dump
```

For repeatable Windows operations, `scripts/backup.ps1` creates a timestamped database/media bundle and SHA-256 manifest. `scripts/restore.ps1` requires an explicit confirmation switch and should only target an isolated restore environment.

The backup bundle must be encrypted before it leaves the application host and copied to an independent destination. The destination must not be the same disk, VM, or credentials boundary as the live application. The backup job must fail if encryption or the off-site copy fails; a local archive alone is not a successful production backup.

## Evidence required before production approval

The release record must contain all of the following, with timestamps and an
identified operator:

- backup job output showing the database and matching private-media archive;
- encryption confirmation and the destination identifier;
- off-site copy confirmation in an independent account or storage boundary;
- SHA-256 manifest for the transferred bundle;
- restore-drill output from an isolated database and media directory;
- verification of login, patient lookup, document download, audit events, and invoice/PDF access after restore;
- measured RPO and RTO, plus any corrective actions.

`backup.ps1` intentionally creates a local bundle and manifest only. It must
not be treated as proof of encrypted off-site backup until the encryption,
transfer, and restore evidence above has been attached to the release record.

## MySQL example

```bash
mysqldump --single-transaction --routines --triggers "$DB_NAME" > pcms-YYYY-MM-DD.sql
mysql "$RESTORE_DATABASE_URL" < pcms-YYYY-MM-DD.sql
```

## Private media

Back up the directory configured by the application as `BASE_DIR/private_media`. It contains clinical documents and patient identification photographs. Restore it together with the database snapshot so `PatientDocument` and `Patient.photo` rows remain consistent.

## Restore drill

At least quarterly:

1. Restore a database backup into an isolated environment.
2. Restore the matching private-media backup.
3. Run migrations and `manage.py check`.
4. Verify login, patient lookup, clinical document download, audit events, and invoice/PDF access.
5. Record restore duration, missing files, errors, and corrective actions.

A backup is not considered reliable until a restore drill succeeds and is recorded.

The historical local rehearsal is recorded in `docs/RESTORE_DRILL_2026-08-22.md`. That record is not a production backup or production restore acceptance.

Production restore is **not** done until a HostPinnacle backup is restored onto isolated staging and verified with a full SHA-256 of the transferred bundle. Do not treat a local `backup.ps1` archive, a truncated hash, or an invented patient count as restore evidence.

## Release handoff

Before each production release, record the latest successful backup timestamp, database engine, private-media location, restore owner, and restore-test result. The release is not approved if the database backup exists without the matching private-media archive.

---
