# PostgreSQL migration policy

Migrations are forward-only in normal deployment and must be individually reversible during development and disaster recovery.

## Canonical order

1. `sql/001_initial.sql` creates the Phase 0 relational substrate.
2. `sql/002_canonical_constraints.sql` adds Behavior plus canonical invariant constraints and indexes.

## Rollback

For development/test rollback, execute the matching `*_down.sql` migration in reverse order. Never delete Experience rows to correct historical data; correction is represented by new Experience records.

## Contract rules

Every persisted entity has a schema version. Temporal intervals reject `valid_to < valid_from`. Derived entities retain provenance. Behavior is downstream and is never a prerequisite for Experience persistence. Embeddings remain an index and never replace canonical content.

## Verification

A clean database must accept migrations 001 then 002. The migration test suite also validates the required DDL markers and invariant constraints so schema drift is detectable without requiring a live PostgreSQL server.
