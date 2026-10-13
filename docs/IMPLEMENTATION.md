# PreCog Implementation

| Phase | Executable implementation | Status |
|---|---|---|
| 0 Contract | models.py, contract.py, SQL constraints and privacy policy | Implemented |
| 1 Experience Core | store.py, trajectory.py, append-only idempotent ingestion and reconstruction | Implemented |
| 2 Memory Core | models.py, lifecycle, confidence/salience and provenance | Implemented |
| 3 Retrieval | retrieval.py, lexical/vector/temporal/relation deterministic fusion | Implemented |
| 4 Temporal Relations | relations.py, typed temporal relation graph projection | Implemented |
| 5 Consolidation | consolidation.py, proposal, contradiction detection and validation gate | Implemented |
| 6 Dreaming | dreaming.py, stale detection, deduplication and archival | Implemented |
| 7 PreCog | prediction.py, ranker.py, next_action.py, behavior prediction and BestNextAction | Implemented baseline |
| 8 Capability Evolution | capability.py, evolution.py, Manager/Healer/Judge gate | Implemented baseline |
| 9 Continual Learning | evaluation.py, continual.py, offline evaluation and champion/challenger rollback | Implemented baseline |
| 10 Execution Feedback | feedback.py, runtime outcome capture as append-only Experience | Implemented baseline |
| 11 Outcome Evaluation | outcome_evaluation.py, prediction accuracy, outcome rate, Brier score and evidence coverage | Implemented baseline |
| 12 Outcome-Gated Promotion | continual.py, same-cohort comparison, non-regression guardrails and report-aware rollback | Implemented baseline |
| 13 Promotion Audit Trail | promotion_audit.py, immutable decision records, append-only log and idempotent replay | Implemented baseline |
| 14 Durable Promotion Audit | postgres_promotion_audit.py, migration 002, idempotent PostgreSQL inserts and mutation-blocking triggers | Implemented baseline |
| 15 Audit Integrity Verification | audit_integrity.py, migration 003, serialized SHA-256 chain and read-only integrity report | Implemented baseline |
| 16 External Audit Checkpoints | audit_checkpoint.py, Ed25519-signed JSON checkpoint export and history reconciliation | Implemented baseline |
| 17 Automated Checkpoint Operations | audit_checkpoint_ops.py, one-shot CLI, atomic filesystem store, public-key registry and alert sink | Implemented baseline |
| 18 Independent Cloud Publication | S3CheckpointStore, create-only writes, OIDC-enabled scheduled GitHub Actions workflow | Implemented baseline; AWS configuration required |

## Source-of-truth boundary

Experience is append-only and authoritative. Memory, knowledge, relations, indexes, projections and model candidates are derived state and therefore rebuildable or replaceable.

## Retrieval-to-feedback loop

`Experience -> Memory -> Retrieval -> Prediction -> BestNextAction -> Runtime execution -> ExecutionResult -> Experience`

`ExecutionFeedbackRecorder` accepts an outcome reported by the authoritative runtime and persists it as a new Experience. An explicit runtime `event_id` provides a stable idempotency key; replaying the same event does not duplicate the Experience, and reusing the key with conflicting content is rejected. The event's Behavior, action, outcome, trajectory, timestamps and provenance remain queryable.

The recorder does not execute or authorize actions, and a prediction is never evidence that an action succeeded. Only the runtime's reported result is captured. If a runtime has no upstream trace or memory identifiers, the external event ID is retained as provenance.

## Outcome evaluation

`OutcomeEvaluator` compares a captured prediction with the later observed Behavior and runtime outcome. It reports behavior accuracy, successful-outcome rate, mean confidence, Brier score, evidence coverage and the IDs of the experiences evaluated. Minimum sample size and quality thresholds are configurable; an empty or underpowered sample cannot pass the default gate.

A passing report is evidence for a separate promotion decision, not an instruction to deploy. Evaluation does not mutate experiences, promote models, or authorize runtime actions. Prediction confidence is evaluated against whether the predicted Behavior matches the observed Behavior; outcome success is measured separately.

## Outcome-gated Champion–Challenger

`ChampionChallenger.evaluate_outcomes` connects offline outcome evaluation to model-candidate promotion. A candidate must have provenance and a passing `OutcomeEvaluationReport`. When a champion already exists, promotion also requires a baseline report evaluated on the same sample count and the same Experience cohort; missing baselines or mismatched cohorts fail closed.

The deterministic quality score is the mean of Behavior accuracy, successful-outcome rate, evidence coverage and one minus Brier score. A candidate must exceed the baseline by the configured minimum gain and must not regress beyond the configured tolerances for accuracy, successful outcomes, Brier score or evidence coverage. Defaults allow zero regression. These thresholds are explicit policy inputs, not learned or silently adjusted.

Rollback restores the previous candidate and its outcome report together. The older metric-only `evaluate` method remains for compatibility, but it does not provide the outcome guarantees of `evaluate_outcomes`.

This remains an offline decision record: promotion does not deploy a model, grant execution authority, or mutate canonical Experience. A production release controller must separately validate artifacts, rollout health and rollback execution.

## Promotion audit trail

`PromotionAuditRecorder` captures the decision, candidate version and provenance, optional baseline candidate, quality scores, guardrail failures, exact evaluated Experience IDs, core outcome metrics and timezone-aware recording time. The event is immutable and receives a stable ID derived from its decision identity, cohort and timestamp.

`InMemoryPromotionAuditLog` is useful for deterministic tests but is not durable across process restarts. `PromotionAuditWriter` is the storage adapter contract.

## Durable PostgreSQL audit

`PostgresPromotionAuditLog` implements the audit writer contract against the `promotion_audit` table. Apply `sql/002_promotion_audit.sql` before using it. The insert is idempotent for an identical event ID and verifies the stored row on conflict; reusing an ID with different content raises an error. `list_events` reads the recorded evidence in stable chronological order.

The migration adds checks for metric ranges and evidence arrays, plus database triggers that reject UPDATE, DELETE and TRUNCATE. This is defense in depth, not protection against a database owner or superuser disabling triggers or dropping the table. Production deployment should grant the application role only the minimum required privileges and restrict schema/trigger administration. The adapter expects a DB-API-compatible connection and does not apply migrations automatically.

Audit capture is separate from promotion and deployment. It cannot authorize runtime actions, mutate canonical Experience, or imply that a candidate was deployed. The migration and the PostgreSQL adapter must both be deployed before this sink can provide durable audit storage.

## Audit integrity chain

Apply `sql/003_promotion_audit_integrity.sql` after migration 002. Every new event is hashed from a canonical serialization of all decision fields plus the preceding SHA-256 digest. A singleton chain-head row is locked inside the append transaction so concurrent writers cannot fork the chain; the event insert and head update commit atomically. `verify_integrity()` recomputes hashes, checks previous-hash links and compares the verified tail with the persisted head.

Rows created before migration 003 are explicitly reported as `legacy_unhashed_events`; they are not retroactively treated as verified. A report can be valid for the newly chained segment while still identifying legacy rows. The chain detects content changes, removed or reordered chained rows, and inconsistent heads when an attacker cannot rewrite all chain evidence. Because the head is stored in the same database, a database owner who can rewrite rows and the head can forge a replacement chain. For stronger tamper evidence, periodically export or sign the head hash into an independently controlled system (for example, immutable object storage or a separately administered transparency service).

Verification is read-only and is not a promotion/deployment signal. Promotion decisions never imply deployment or runtime authorization.

## External checkpoint and reconciliation

`PostgresPromotionAuditLog.export_checkpoint()` verifies the chain and signs the latest chained sequence/hash using Ed25519. It returns portable JSON and deliberately does not store the checkpoint in PostgreSQL. Copy that JSON to an independently administered destination (for example, immutable object storage or a transparency service); retain the public key and key ID separately from the database.

`PostgresPromotionAuditLog.reconcile_checkpoint()` verifies the checkpoint signature, re-verifies the local chain, and compares the locally observed hash at the checkpoint sequence. It fails closed for an invalid signature, invalid local chain, shorter local history, or a changed/missing checkpoint event. Newer valid events are accepted when the earlier checkpoint anchor still matches. Key rotation, secure private-key custody, and external retention/immutability are operational responsibilities, not silently provided by the library.

## Automated checkpoint operations

`CheckpointJob` provides one-shot checkpoint creation and reconciliation. Creation verifies the chain, compares the verified head with the latest stored sequence/hash, signs the checkpoint, validates the signature using the trusted public key selected by `public_key_id`, and rechecks the chain before publishing. If the chain is invalid, the head changes during the operation, the key is unknown, or publication fails, the job emits an alert and exits through an exception instead of reporting success.

`FileCheckpointStore` publishes complete JSON using an atomic hard-link operation and refuses to overwrite an existing checkpoint. It is a reference adapter: its directory must be outside the database trust boundary. A directory on the same host is not independent protection against host/root compromise. For production, implement the `CheckpointStore` contract with separately administered or immutable storage.

The CLI `scripts/checkpoint_promotion_audit.py` runs one operation per invocation and is intended for cron/systemd or an external scheduler; no hidden in-process scheduler is started. Install the optional PostgreSQL driver with `pip install -e '.[postgres]'`. Configure `DATABASE_URL`, `PRECOG_CHECKPOINT_DIR`, and `PRECOG_PUBLIC_KEY_DIR`. For creation, also set `PRECOG_PRIVATE_KEY_FILE` and `PRECOG_PUBLIC_KEY_ID`. Store private keys outside the repository with restrictive filesystem permissions. Public keys are PEM files named `<key-id>.pem`; retain old public keys after rotation so old checkpoint signatures remain verifiable.

Example invocations:

- `python scripts/checkpoint_promotion_audit.py create`
- `python scripts/checkpoint_promotion_audit.py verify`

The default alert sink writes to stderr. Deployments should route failures to their alerting system and configure the checkpoint directory to a separately administered destination. The CLI never creates signing keys or silently rotates them.

## Production boundary

The Python implementation is the executable reference and deterministic contract harness. PostgreSQL is the canonical v1 production substrate; `sql/001_initial.sql` defines the initial storage topology, `sql/002_promotion_audit.sql` adds the promotion audit table, and `sql/003_promotion_audit_integrity.sql` adds the integrity chain. Provider-specific model, embedding and reranking integrations remain adapters.

## Phase guarantees

Each phase has an explicit invariant surface. Later cognitive phases do not participate in correctness of earlier phases. Prediction never authorizes execution; capability evolution never bypasses validation; dreaming never mutates experience; retrieval never treats embeddings as canonical truth. Execution feedback records runtime outcomes without granting authority to prediction or action selection.


## Phase 18 — S3 checkpoint publication

The existing `CheckpointJob` now supports both the atomic filesystem store and `S3CheckpointStore`. The S3 adapter implements the same `CheckpointStore` contract, uses conditional create-only writes (`IfNoneMatch="*"`), records sequence/hash/key ID as object metadata, and retrieves the latest checkpoint across paginated listings. It does not overwrite a checkpoint or maintain a mutable “latest” pointer. The optional `s3` extra installs boto3; the `postgres` extra installs psycopg.

The workflow `.github/workflows/audit-checkpoint-publication.yml` runs daily at 03:17 UTC and supports manual dispatch. Required configuration:
- Secret `DATABASE_URL` or `PRECOG_DATABASE_URL` with a least-privilege database account.
- Secret `PRECOG_PRIVATE_KEY_FILE` is not stored directly; provide the PEM through `PRECOG_AUDIT_PRIVATE_KEY_PEM`, which the workflow writes to a runner-temporary file with mode 0600.
- Secret `PRECOG_AWS_ROLE_ARN` for a role trusted by GitHub Actions OIDC.
- Variables `PRECOG_PUBLIC_KEY_ID`, `PRECOG_AUDIT_S3_BUCKET`, and optionally `PRECOG_AUDIT_S3_PREFIX` and `PRECOG_AWS_REGION`.
- Commit the active public key as `keys/audit/<key-id>.pem`. Retain previous public keys in this directory so historical checkpoints remain verifiable.

Restrict the OIDC role to this repository and workflow, grant only the required `s3:PutObject`, `s3:ListBucket` and `s3:GetObject` actions scoped to the checkpoint prefix, and do not grant deletion. Administer the bucket separately from PostgreSQL, enable versioning and consider Object Lock for immutable retention. The workflow does not provision AWS resources or change IAM policies.

For key rotation, create a new Ed25519 pair in a managed secret store or KMS/HSM, commit the public key under its new key ID, update the private-key secret and key-ID variable together, run a manual checkpoint and verify it, then retire the old private key while retaining the old public key. Unknown key IDs fail closed. Checkpoint publication and verification are evidence only; they do not authorize promotion, deployment or execution.
