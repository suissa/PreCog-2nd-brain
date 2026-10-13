# External audit checkpoint operations

## Publication and verification

The publication workflow creates a signed Ed25519 checkpoint daily and on manual dispatch. A separate verification workflow runs daily after publication and can be dispatched manually. Verification uses a dedicated AWS role and should not be able to write or delete objects.

The verifier checks the local PostgreSQL audit chain, the external checkpoint signature and trusted key ID, the historical hash at the checkpoint sequence, and the configured freshness budget. It fails on a missing checkpoint, unknown key, invalid signature, rollback/truncation, changed historical hash, invalid local chain, stale checkpoint, or excessive sequence lag.

Defaults are **PRECOG_MAX_CHECKPOINT_AGE_HOURS=36** and **PRECOG_MAX_CHECKPOINT_LAG_EVENTS=1000**. Configure these as repository variables when appropriate for the audit event volume and publication cadence. A checkpoint may naturally trail the current database head; this is not tampering by itself. It becomes an operational alert only when the configured age or event-lag budget is exceeded. Hash/signature mismatch remains an integrity failure regardless of freshness.

## Required configuration

- Secrets: **PRECOG_DATABASE_URL** (or **DATABASE_URL**), **PRECOG_AUDIT_VERIFY_AWS_ROLE_ARN**.
- Variables: **PRECOG_PUBLIC_KEY_ID**, **PRECOG_AUDIT_S3_BUCKET**; optional **PRECOG_AUDIT_S3_PREFIX**, **PRECOG_AWS_REGION**, **PRECOG_MAX_CHECKPOINT_AGE_HOURS**, **PRECOG_MAX_CHECKPOINT_LAG_EVENTS**.
- Public key: **keys/audit/<PRECOG_PUBLIC_KEY_ID>.pem**, committed to the repository. Retain old public keys to verify historical checkpoints.
- AWS verifier role: **s3:ListBucket** scoped to the checkpoint prefix and **s3:GetObject** scoped to objects under that prefix. Do not grant **s3:PutObject** or delete permissions to this role.

GitHub Actions marks a failed verification run as failed and emits the actionable cause to stderr, which is available in the run logs. This workflow does not create issues or send external notifications; configure GitHub Actions failure notifications if additional paging is required. It does not authorize promotion, deployment, or runtime execution.
