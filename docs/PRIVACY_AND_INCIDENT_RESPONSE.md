# Privacy and incident response controls

This system handles patient identity, clinical notes, documents, appointments, audit events, inventory, and financial records. Access is role-scoped and clinical media is private.

## Data lifecycle

- Keep active-care records available for care delivery and legal/clinical continuity.
- Define the final retention period with the hospice data-protection owner and legal adviser before production approval; record the approved period in the retention register.
- Do not hard-delete clinical records from the application. Use an approved archival or anonymization process with a reason, approver, timestamp, and audit event.
- Private media must be retained and destroyed with the matching database record under the same approved schedule.

## Export and access requests

- Full patient and encounter exports are management-only and create `EXPORT` audit events.
- Validate the requester's identity, authority, scope, and destination before releasing an export.
- Use an encrypted transfer channel, expiry/delete the working copy, and record who approved, generated, received, and destroyed the export.
- Never send clinical exports through ordinary email or store them in public media.

## Incident response

1. Detect and preserve evidence: request ID, audit events, access logs, affected record IDs, and timestamps.
2. Contain: disable compromised accounts, rotate credentials, revoke sessions, restrict media/database access, and preserve backups.
3. Assess scope: identify patients, fields, media, users, and time window affected.
4. Escalate to the hospice incident owner and data-protection/legal adviser; follow the applicable notification deadlines.
5. Recover from a verified backup only after preserving evidence and approving the recovery plan.
6. Document root cause, corrective actions, notification decisions, and a post-incident access review.

## Security evidence

Audit events are application-immutable and admin read-only. Production log collection must be centralized, access-controlled, retained under the approved schedule, and monitored for repeated login failures, MFA failures, rate-limit responses, unexpected 5xx errors, and private-media access anomalies.
