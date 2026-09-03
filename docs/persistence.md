# Persistence and aggregated dashboard flow

SQLite persistence is local to one company deployment. The default database is
`storage/tracker.sqlite3`; override it with `DATABASE_PATH`. Keep the database and its WAL
sidecars on the same machine as the FastAPI process.

## Incremental ingestion

`POST /api/v1/analyze-tables` treats every request as an incremental upsert batch:

1. Pydantic validates the `{ "tables": [...] }` envelope.
2. The service stores an immutable pending submission with the full request JSON, checksum,
   schema fingerprint, optional `Idempotency-Key`, and row counts.
3. A persisted plan is reused for a known schema; otherwise the bounded mapping agent creates and
   validates one.
4. Python binds canonical evidence, collapses identical same-ID rows, rejects conflicting same-ID
   rows, validates the batch, and calculates an audit response.
5. One transaction stores the reusable mapping plan, immutable per-submission plan snapshot,
   audit response, canonical record upserts, and completed status.
6. The endpoint returns `201 Created` with a compact `SubmissionReceipt`.

Failed submissions retain their raw request and bounded error but publish no canonical evidence.
Pending and failed rows never contribute to dashboard reads.

A KPI evidence batch may omit employee and performance-target tables when completed canonical
employee and target records already exist. Plan validation accepts those persisted foundations,
then the dashboard joins the new evidence to the combined canonical dataset. The first KPI
submission still requires both foundations, and missing employee IDs or targets remain visible
through deterministic validation and confidence gating.

This is a plan-validation allowance, not an implicit join performed by the model. The partial
batch is mapped and stored under its own schema fingerprint. During dashboard retrieval, Python
materializes its canonical evidence together with the previously stored employee and target
records, then validates relationships and calculates the combined result.

Use a deployment-wide `Idempotency-Key` header for webhook delivery. Reusing a key returns the
original receipt and does not create or publish another submission. Without a key, repeated
requests are independently audited, while stable record identities still prevent evidence from
being counted twice.

## Cache and recalculation boundaries

The in-memory and SQLite mapping caches store validated table classifications, approved calculator
choices, and field bindings by schema fingerprint. A mapping-cache hit skips only the mapping-model
request. It does not skip raw-request persistence, canonical upserts, duplicate detection, source
validation, or KPI calculation. Unless an `Idempotency-Key` identifies a replay, every accepted
request is retained as a separate submission.

An unseen but small schema can be substantially faster than a large first submission even when
both make one model request: the synopsis uses fewer tokens, Python binds fewer tables and rows,
and SQLite publishes fewer records. Use the persisted `model_requests`, `total_tokens`, and
`mapping_cache_hit` audit fields to distinguish smaller work from actual plan reuse.

Dashboard GET requests have a separate boundary: they never call the mapping model and do not
return cached KPI responses. Each GET loads current canonical evidence, applies its filters, and
runs deterministic validation and calculation for that requested scope.

## Canonical merge and correction precedence

Current state is unique by `(record_type, record_id)`. Employee and performance-target identities
use `employee_id`; event families use their canonical `record_id`. Overlapping batches are safe:
new identities insert, repeated identities upsert, and omitted identities remain active.

For a correction, precedence is:

1. A greater mapped `source_version`.
2. When versions do not decide, a later mapped `source_updated_at`.
3. When neither side supplies source ordering, submission completion time.

An unversioned late delivery cannot replace a versioned current row. SQLite enforces the identity
constraint and update predicate atomically, including concurrent writers.

Inside one batch, identical same-ID rows collapse and produce an excluded-duplicate finding.
Conflicting same-ID rows produce an error and that identity is not published. Equal content under
different IDs is flagged for review but retained because two real events may legitimately match.

Deletion events are not supported. A future `period_snapshot` contract must explicitly declare
its coverage before absence can tombstone current records; omission from an incremental batch is
never interpreted as deletion.

## Aggregated dashboard

`GET /api/v1/dashboard` loads all canonical current-state payloads from completed submissions,
validates each payload into its evidence-specific Pydantic model, and constructs one combined
`PerformanceEvidenceDataset`. Python then runs validation and KPI calculation once over the
requested scope. It never averages previously calculated submission scores and never invokes the
mapping model.

Supported filters are `employee_id`, case-insensitive `team`, explicit inclusive `start_date` and
`end_date`, or `period_weeks=4|8|12`. Week presets and explicit dates are mutually exclusive. A
preset is anchored to the combined evidence's latest business date:

```text
effective_end = combined coverage end
effective_start = max(combined coverage start, effective_end - (period_weeks * 7 - 1 days))
```

The resolved dates are returned in `applied_filters`. Results, summary averages, confidence,
alerts, supporting evidence, and trends all use that same scope. Employee and team options are
computed from the unfiltered combined dimensions so filters remain usable after a narrow response.

The dedicated `DashboardResponse` also returns combined coverage, contributing-submission count,
latest completion time, and mapping summaries grouped by schema fingerprint. If contributing
schemas expose different optional bindings for one evidence family, the materializer uses only
the shared mapped fields and returns a limitation instead of silently changing confidence rules.

## Stored tables

- `submissions`: immutable request JSON, delivery metadata, and processing status.
- `mapping_plans`: reusable validated plan cache keyed by schema fingerprint.
- `submission_plans`: immutable plan snapshot used by each completed submission.
- `analysis_runs`: complete deterministic batch response retained for audit and regression review.
- `canonical_records`: current evidence version, business dates, source ordering, and provenance.

Migrations `001_initial.sql` and `002_aggregated_evidence.sql` apply automatically. SQLite uses WAL
mode, foreign keys, a five-second busy timeout, and short-lived transactional connections.

Insight contexts remain bounded and process-local for 15 minutes. Each dashboard calculation
creates a fresh `analysis_id`; `/insights` remains the only optional dashboard-initiated model call.

## Report data and retention

`POST /api/v1/reports/employee/preview` reads canonical state through the same filtered dashboard
materialization path and returns a renderer-ready snapshot with `Cache-Control: no-store`. It does
not add a report table, save the preview, or persist a PDF. The optional prior-period comparison is
recalculated from canonical evidence when a complete, non-overlapping prior period falls within
available coverage.

The browser generates employee, team, and KPI PDFs with `pdfmake`. Team and KPI reports consume
the current filtered `DashboardResponse` directly, so they create no additional backend reads or
stored artifacts. Saved reports, download history, scheduled delivery, and retention/deletion
policies require a future persistence design and are not part of the current implementation.

## Railway production

Railway's normal service filesystem is ephemeral. Attach one Railway Volume to the FastAPI
service, mount it at `/data`, and configure:

```env
DATABASE_PATH=/data/tracker.sqlite3
```

The variable alone does not provide persistence. Keep the service at one replica because Railway
Volumes are single-service storage, and enable Volume backups. If a non-root container receives
volume permission errors, set `RAILWAY_RUN_UID=0`; otherwise leave it unset.
