# External audit checkpoint operations

## Publication, verification, and incident alerts

The publication workflow creates a signed Ed25519 checkpoint daily and on manual dispatch. A separate verification workflow runs daily after publication and can be dispatched manually. Verification uses a dedicated AWS role and should not be able to write or delete objects.

The verifier checks the local PostgreSQL audit chain, the external checkpoint signature and trusted key ID, the historical hash at the checkpoint sequence, and the configured freshness budget. It fails on a missing checkpoint, unknown key, invalid signature, rollback/truncation, changed historical hash, invalid local chain, stale checkpoint, or excessive sequence lag.

Defaults are **PRECOG_MAX_CHECKPOINT_AGE_HOURS=36** and **PRECOG_MAX_CHECKPOINT_LAG_EVENTS=1000**. Configure these as repository variables when appropriate for the audit event volume and publication cadence. A checkpoint may naturally trail the current database head; this is not tampering by itself. It becomes an operational alert only when the configured age or event-lag budget is exceeded. Hash/signature mismatch remains an integrity failure regardless of freshness.

## Incident lifecycle

The workflow uses one open issue titled **[Audit Monitor] External checkpoint verification failing** to avoid duplicate incidents. Each failed scheduled/manual run appends a comment with the run URL and commit. The next successful verification comments on and closes the incident. Failures in configuration, AWS authentication, dependency installation, or reconciliation are also tracked because the incident step evaluates the overall job status.

For optional external notifications, configure the repository secret **PRECOG_AUDIT_ALERT_WEBHOOK_URL** with an HTTPS webhook URL that accepts a JSON payload containing a `text` field (for example, a compatible chat incoming webhook). It sends only on incident creation and recovery, not on every repeated failure. Webhook delivery errors are warnings and do not suppress GitHub incident tracking or overwrite the verification result. Without the secret, issue tracking still works. The workflow requires `issues: write` for incident tracking, plus its existing read and OIDC permissions.

## Required configuration

- Secrets: **PRECOG_DATABASE_URL** (or **DATABASE_URL**), **PRECOG_AUDIT_VERIFY_AWS_ROLE_ARN**; optional **PRECOG_AUDIT_ALERT_WEBHOOK_URL**.
- Variables: **PRECOG_PUBLIC_KEY_ID**, **PRECOG_AUDIT_S3_BUCKET**; optional **PRECOG_AUDIT_S3_PREFIX**, **PRECOG_AWS_REGION**, **PRECOG_MAX_CHECKPOINT_AGE_HOURS**, **PRECOG_MAX_CHECKPOINT_LAG_EVENTS**.
- Public key: **keys/audit/<PRECOG_PUBLIC_KEY_ID>.pem**, committed to the repository. Retain old public keys to verify historical checkpoints.
- AWS verifier role: **s3:ListBucket** scoped to the checkpoint prefix and **s3:GetObject** scoped to objects under that prefix. Do not grant **s3:PutObject** or delete permissions to this role.

Incident tracking and notifications report operational status only. They do not authorize promotion, deployment, or runtime execution.
