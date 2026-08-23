# Restore drill record — 2026-08-22

## Scope

Historical local isolated rehearsal using a SQLite database artifact and a
private-media copy. This record is retained as historical evidence only; it
is not a production backup or production restore acceptance record.

## Result

- Database: PASS for the historical local rehearsal.
- Private media: PASS for the historical local rehearsal.
- Production RPO/RTO: not established by this rehearsal.

## Limitation and next required drill

Before rollout, repeat against the actual staging PostgreSQL/MySQL backup and
private object/filesystem store. Record encryption, independent off-site copy,
backup age as RPO, full restore-to-service duration as RTO, and verification of
login, patient lookup, clinical document download, audit events, and invoice/PDF
access. Do not retain patient data or backup hashes in the source workspace.
