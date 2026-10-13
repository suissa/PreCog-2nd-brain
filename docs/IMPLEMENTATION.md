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
| 16 External Audit Checkpoints | audit_checkpoint.py, Ed25519-signed JSON checkpoint export and history reconciliation | Implemented baseline |\n| 17 Automated Publication and Key Rotation | audit_checkpoint_store.py, audit_keyring.py, scheduled GitHub Actions publisher to S3 | Implemented baseline; deployment configuration required |

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

## Production boundary

The Python implementation is the executable reference and deterministic contract harness. PostgreSQL is the canonical v1 production substrate; `sql/001_initial.sql` defines the initial storage topology, `sql/002_promotion_audit.sql` adds the promotion audit table, and `sql/003_promotion_audit_integrity.sql` adds the integrity chain. Provider-specific model, embedding and reranking integrations remain adapters.

## Phase guarantees

Each phase has an explicit invariant surface. Later cognitive phases do not participate in correctness of earlier phases. Prediction never authorizes execution; capability evolution never bypasses validation; dreaming never mutates experience; retrieval never treats embeddings as canonical truth. Execution feedback records runtime outcomes without granting authority to prediction or action selection.

The normative specification remains PRE-CORD.md; the roadmap remains ROADMAP.md.


## Automated external checkpoint publication

`scripts/publish_audit_checkpoint.py` verifies the PostgreSQL hash chain, creates an Ed25519-signed checkpoint and publishes it to S3. The optional `audit-publish` extra installs `psycopg` and `boto3`; core imports do not require either package. `S3CheckpointPublisher` uses a create-only `IfNoneMatch="*"` write and a unique object key containing sequence, head hash and checkpoint timestamp. It never updates a mutable “latest” object. A failed conditional write fails closed.

The scheduled workflow is `.github/workflows/audit-checkpoint-publication.yml` (daily at 03:17 UTC) and can also be run manually. Before enabling it, configure:
- Repository secret `PRECOG_DATABASE_URL` with a least-privilege PostgreSQL account allowed to read the audit chain.
- Repository secret `PRECOG_AUDIT_PRIVATE_KEY_PEM` containing the Ed25519 private key in PEM form; never commit this value or upload it as an artifact.
- Repository secret `PRECOG_AWS_ROLE_ARN` for an AWS role trusted by GitHub Actions OIDC.
- Repository variable `PRECOG_AUDIT_KEY_ID`, a stable non-secret identifier for the current signing key.
- Repository variable `PRECOG_AUDIT_S3_BUCKET` and optionally `PRECOG_AUDIT_S3_PREFIX` and `PRECOG_AWS_REGION`.

Restrict the OIDC role to this repository/workflow and the checkpoint prefix, grant only `s3:PutObject`, and do not grant object deletion. Keep the bucket in a separate administrative/security boundary from PostgreSQL; enable versioning and consider S3 Object Lock for the required retention period. The workflow deliberately does not create AWS infrastructure or configure IAM policies.

### Key rotation and verification

`AuditPublicKeyring` stores public-key records with `active`, `verify_only` and `revoked` states. Exactly one key at most can be active; historical `verify_only` keys remain usable for existing checkpoint signatures. Unknown and revoked key IDs fail verification. The keyring contains public keys only.

To rotate: create a new Ed25519 key pair in a managed secret store or KMS/HSM; publish and independently retain the new public key; add it to verifier keyrings; update `PRECOG_AUDIT_PRIVATE_KEY_PEM` and `PRECOG_AUDIT_KEY_ID` together; run a manual publication and verify its signature with the new public key; then retire the old private key while retaining the old public key as `verify_only`. Mark a key `revoked` only when policy says its signatures must no longer be trusted. Record the rotation out of band and restrict access to both the secret and the workflow configuration.

The workflow does not automatically verify remote checkpoints against a verifier keyring, provision S3, create KMS keys, or configure Object Lock. These remain deployment controls. Publication failures surface as failed workflow runs; they must be monitored. A checkpoint is tamper-evidence only and never authorizes promotion, deployment or execution.
