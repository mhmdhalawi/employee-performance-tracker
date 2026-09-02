# Multi-submission dashboard aggregation plan

## Goal

Treat each successful `POST /api/v1/analyze-tables` call as an incremental ingestion batch while
presenting one combined, recalculated dataset through `GET /api/v1/dashboard`.

If Monday and Tuesday are submitted separately, the dashboard must behave as though the current
versions of both days' source records were submitted together. Employee, team, and reporting-period
filters must request a new result from the backend. Python remains authoritative for validation,
confidence, KPI scores, summaries, alerts, and weekly trends.

This intentionally expands the current project boundary in `AGENTS.md` and `docs/persistence.md`,
which says that cross-submission aggregation is out of scope and that the dashboard reads only the
latest completed submission. Update those documents when this plan is implemented.

## Required behavior

- Preserve every original webhook request unchanged for audit and troubleshooting.
- Publish only successfully completed submissions into the combined dashboard dataset.
- Combine canonical evidence records, not previously calculated KPI responses.
- Recalculate the requested dashboard view from the combined evidence; never average daily KPI
  scores.
- Treat the webhook contract as incremental upserts. A later record with the same stable identity
  corrects or replaces the earlier version.
- Use business dates inside evidence records for period filtering, not webhook receipt time.
- Keep pending and failed submissions out of dashboard reads.
- Keep all deterministic arithmetic in Python. The frontend only sends filter choices and renders
  the returned result.

## Data ownership and merge rules

The first implementation will use one deployment-wide ingestion rule: every request is an
incremental upsert batch. Each batch must remain independently mappable under the existing agent
planning rules.

Canonical identities are:

| Record type | Stable identity | Dashboard date |
| --- | --- | --- |
| Employee | `employee_id` | Not date-filtered |
| Performance target | `employee_id` | Not date-filtered |
| Work output | `record_id` | `assigned_date` |
| Attendance | `record_id` | `occurred_on` |
| Required report | `record_id` | `due_date` |
| Leave | `record_id` | Overlaps `start_date` through `end_date` |
| Quality review | `record_id` | `occurred_on` |

Merge records by `(record_type, stable_identity)`:

1. A new identity is inserted into the canonical current state.
2. An existing identity with identical content is an idempotent replay and does not create a
   second evidence record.
3. An existing identity with changed content is a correction; the most recently completed
   submission becomes the current version.
4. The immutable raw submissions retain previous versions for audit.
5. Identical same-ID rows inside one batch collapse to one canonical record and produce an
   excluded-duplicate finding.
6. Conflicting same-ID rows inside one batch produce a validation error; do not publish an
   arbitrary winner for that identity.
7. Deletion/tombstone events are not part of the initial contract. A later contract extension is
   required if source records must be explicitly removed.

This record-ID merge happens before `validate_dataset` so webhook retries and corrections do not
produce false `duplicate_record_id` findings. Existing duplicate-attendance detection by employee
and work date still runs after the merge and keeps its current production behavior.

### Database-level duplicate protection

Enforce canonical identity in SQLite:

```sql
UNIQUE (record_type, record_id)
```

Write canonical records with an atomic `INSERT ... ON CONFLICT DO UPDATE`. Update an existing row
only when the incoming `source_version` or `source_updated_at` is newer; use submission completion
time as the documented fallback when neither is supplied. SQLite then guarantees that concurrent
requests cannot commit two current-state rows with the same canonical identity.

This guarantee applies to canonical current state, not immutable raw-submission history. Raw
submissions intentionally retain repeated deliveries and old versions for audit. Different record
IDs that describe the same real-world event require family-specific validation and must not be
silently merged using a generic content hash.

For example, if week 1 contains `ATT-001`, `ATT-002`, and `OUT-001`, then a later weeks 1-and-2
submission containing those IDs plus `ATT-003`, `ATT-004`, and `OUT-002` produces six canonical
records, not nine. Repeated IDs are upserts; only new IDs increase the record count.

Use separate safeguards for each duplicate case:

1. **Whole-request retry:** the same deployment-wide `Idempotency-Key` returns the original receipt
   without performing a second write.
2. **Overlapping batches:** stable record identities are upserted, so previously submitted weeks
   may safely appear again.
3. **Exact duplicate content under different IDs:** flag it for review, but do not automatically
   merge it because two legitimate events can have equal values.
4. **Correction ordering:** prefer a source-provided version or `source_updated_at`; otherwise use
   submission completion time as the deterministic fallback.

The initial contract treats overlap as incremental upserts, so records omitted from a later request
remain active. If the fixed company feed later needs authoritative replacement snapshots, add an
explicit `period_snapshot` mode with a declared coverage range. Only that mode may tombstone
previous records in its record-type/date scope that are absent from the new snapshot. Never infer
replacement behavior merely because a request repeats an earlier week.

## Target request flow

```text
POST incremental tables
  -> validate request envelope
  -> create immutable pending submission
  -> resolve/validate mapping plan
  -> build canonical PerformanceEvidenceDataset for the batch
  -> run deterministic validation and calculation for the ingestion audit
  -> atomically publish valid canonical record versions and complete the submission
  -> return a small submission receipt

GET dashboard with filters
  -> load canonical current-state records
  -> construct one combined PerformanceEvidenceDataset
  -> resolve the requested employee/team/date scope
  -> validate and calculate once in Python
  -> return the complete filtered dashboard response
```

### Model-use boundary

- Dashboard reads never call an LLM. They load canonical records from SQLite and use deterministic
  Python validation and calculators for filters, KPIs, confidence, summaries, alerts, and trends.
- Ingestion may call the mapping agent for the first unseen schema. Later submissions with the same
  fixed schema reuse its persisted, validated calculation plan, including after a process restart.
- If the company contract becomes fully fixed and explicitly bound in code, ingestion can also use
  a predefined validated plan without an LLM. That would be an intentional change to the current
  AI-classification boundary and must be reflected in `AGENTS.md` when implemented.
- `/insights` remains the only optional dashboard-initiated model call, and only runs when guidance
  is explicitly requested. It does not calculate or change dashboard values.

## API contract

### Ingestion response

Keep `POST /api/v1/analyze-tables` for compatibility, but change its success response from the
complete `AnalysisResponse` to a typed receipt after the database transaction commits:

```http
HTTP/1.1 201 Created
```

```json
{
  "submission_id": "4d5c0d52-...",
  "status": "completed",
  "received_at": "2026-09-02T08:30:00Z",
  "coverage_start": "2026-09-01",
  "coverage_end": "2026-09-02"
}
```

Add a deployment-wide `Idempotency-Key` header before treating this as a production webhook. A
repeated key must return the original receipt and must not create or republish another submission.
Processing is currently synchronous, so use `201 Created`; use `202 Accepted` only if background
processing is introduced later.

### Dashboard filters

Continue to expose `GET /api/v1/dashboard`, with these backend-owned query parameters:

- `employee_id`: optional exact employee identifier.
- `team`: optional team value, matched using the existing case-insensitive behavior.
- `period_weeks`: optional supported preset (`4`, `8`, or `12`).
- `start_date` and `end_date`: optional explicit inclusive range.

`period_weeks` and explicit dates are mutually exclusive. For a week preset, the backend anchors
the range to the latest business date in the combined evidence, not the current clock date:

```text
effective_end = combined coverage end
effective_start = max(combined coverage start, effective_end - (period_weeks * 7 - 1 days))
```

The backend returns the resolved dates in `applied_filters`. This removes date arithmetic from
`PerformanceDashboard.vue` and guarantees that every dashboard client uses the same week boundary.
The existing explicit `start_date`/`end_date` behavior remains available for API consumers and
future custom-date UI.

All filters must affect the same recalculation:

- employee rows and component/overall scores;
- summary counts and averages returned by the backend;
- evidence confidence and status gating;
- validation findings and alert counts;
- supporting record IDs and evidence links;
- weekly KPI trend points.

Sorting, page size, and pagination can remain local presentation state for the current dataset
size. If they later move to the backend, summary cards and trends must still describe the entire
filtered population rather than only the returned page.

### Dashboard response

Create a dedicated `DashboardResponse` schema instead of making a combined view pretend to be one
submission's `AnalysisResponse`. Reuse the existing result, summary, overview, filter, trend,
alert, validation, and limitation models. Add:

- combined `coverage_start` and `coverage_end`;
- `included_submission_count` and `latest_submission_at`;
- backend-provided employee and team filter options computed before applying the selected filters;
- aggregation-aware mapping summaries grouped by schema fingerprint.

Keep `analysis_id` as the temporary key for on-demand employee insights. Build its insight context
from the filtered combined results exactly as the current dashboard restoration path does.

The current `model`, token-usage, `mapping_cache_hit`, `selected_tables`, and
`table_classifications` fields describe one analysis run and are ambiguous for a combined view.
Move mapping information into per-schema summaries, or retain the old fields only during a
documented compatibility window.

## Persistence changes

Add a numbered migration, expected to be `migrations/002_aggregated_evidence.sql`.

1. Extend submission metadata with an optional, deployment-wide idempotency key that is unique
   whenever present.
2. Persist an immutable calculation-plan snapshot per completed submission. The existing
   `mapping_plans` table remains the schema-fingerprint cache, but mutable cache rows must not be
   the only historical record of which plan a submission used.
3. Add canonical current-state record storage with these common fields:
   `record_type`, `record_id`, `employee_id`, `period_start`, `period_end`, `payload_json`,
   `source_version`, `source_updated_at`, `source_submission_id`, and `updated_at`.
4. Make `(record_type, record_id)` unique and index employee/date lookup columns.
5. Validate each `payload_json` back into its specific Pydantic evidence model when constructing a
   combined `PerformanceEvidenceDataset`.
6. Publish canonical upserts, the per-submission plan snapshot, the audit analysis run, and the
   submission's completed status in one transaction so dashboard readers never see a partial
   batch.

Using canonical payload JSON keeps the database layer mechanical and avoids creating a second set
of KPI rules in SQL. SQL selects the current records and relevant date range; Pydantic validates
them; Python calculators own all business logic.

## Backend implementation phases

### Phase 1: Separate ingestion artifacts from response construction

- Refactor `app/services/agent.py` so planning/binding can return an internal typed artifact that
  contains the validated `CalculationPlan`, canonical `PerformanceEvidenceDataset`, mapping/import
  issues, and calculated response.
- Keep public Pydantic response models in `app/schemas/`; keep internal orchestration types private
  to services where appropriate.
- Preserve the current upload endpoint behavior unless it is separately retired. Uploads remain
  request-scoped and do not enter cross-submission aggregation.

### Phase 2: Persist canonical current state

- Add the migration and typed storage operations in `app/core/storage.py`.
- Update `app/services/submissions.py` to publish canonical rows only after successful mapping and
  deterministic validation.
- Implement idempotency lookup and a `SubmissionReceipt` response model.
- Keep raw `request_json` and per-submission `analysis_runs.response_json` for audit and regression
  comparison.

### Phase 3: Build the combined dataset

- Add a pure merge/materialization service that loads canonical rows into one
  `PerformanceEvidenceDataset`.
- Resolve employee and target dimensions independently of event dates.
- Preserve the existing event-date semantics used by `calculate_kpis` and
  `calculate_weekly_kpi_trends`.
- Preserve record provenance so supporting record IDs and evidence links remain traceable to the
  submission that supplied the current version.
- Define conservative mapped-field behavior for mixed schemas. The initial safe rule is to require
  compatible calculator bindings for submissions contributing to the same evidence family; expose
  a limitation instead of silently changing confidence semantics when bindings conflict.

### Phase 4: Replace latest-snapshot dashboard reads

- Replace `load_latest_dashboard()` with storage queries for canonical current-state records and
  aggregation metadata.
- Change `get_latest_dashboard()` into an aggregated dashboard service; rename the function to
  reflect behavior while retaining the HTTP path.
- Resolve `period_weeks` server-side, validate all filters against unfiltered combined facets, and
  pass one effective scope through deterministic validation/calculation.
- Return backend-calculated summaries rather than recomputing summary-card averages in Vue.
- Ensure the mapping agent is never invoked during dashboard reads, including after restart.

### Phase 5: Update the Vue client

- Extend `DashboardFilters` with `period_weeks` and remove client-side conversion of 4/8/12 weeks
  into dates.
- Continue sending a debounced request whenever employee, team, or period changes.
- Render `applied_filters` and backend-provided filter options from the returned response.
- Remove redundant local employee/team filtering and local KPI-average calculations once the
  backend response contains the filtered rows and summary metrics.
- Keep sorting, pagination, request cancellation, loading, empty, and API-error behavior in Vue.
- Update the data-interpretation view to show per-schema mapping summaries when more than one
  source schema contributes to the combined dataset.

## Tests and acceptance criteria

### Persistence and merge tests

- Monday-only submission produces Monday results.
- Adding a Tuesday-only submission makes the full dashboard contain Monday and Tuesday evidence.
- Submitting week 1 followed by weeks 1 and 2 counts the repeated week 1 identities once.
- Combined KPI values equal one deterministic calculation over the merged records, not the average
  of the two daily responses.
- Replaying the same idempotency key does not add records or change results.
- Resending the same record ID with changed content replaces its canonical version and changes the
  recalculated result once.
- Concurrent upserts leave exactly one current-state row per `(record_type, record_id)`.
- An older source version arriving late cannot overwrite a newer canonical version.
- Pending and failed submissions never appear in the dashboard.
- Raw requests and prior analysis snapshots remain queryable in SQLite for audit.
- A process restart produces the same combined dashboard without a mapping-model call.

### Filter tests

- Employee filtering works when that employee's evidence spans several submissions.
- Team filtering includes employees and records from every contributing submission.
- `period_weeks=4`, `8`, and `12` resolve against combined coverage and return their effective dates
  in `applied_filters`.
- Explicit inclusive date ranges work across submission boundaries.
- `period_weeks` combined with explicit dates returns a typed `400` filter error.
- Late-arriving Monday evidence submitted on Wednesday is included in a Monday-based date range.
- Summary, confidence, alerts, supporting evidence, and weekly trends all reflect the same filters.
- Filter options remain usable after a filtered response and are derived from the combined
  unfiltered dataset.
- Unknown employee/team and reversed date ranges retain consistent typed errors.

### Regression and frontend verification

- Keep the existing deterministic performance and 30-employee benchmark suites passing.
- Replace latest-dashboard integration assertions with combined-dashboard assertions while
  retaining single-submission parity coverage.
- Add tests for correction precedence, ambiguous within-batch IDs, and schema-binding conflicts.
- Run `uv run python -m unittest discover -s tests -v`.
- Run `pnpm build` from `web/`.
- Exercise the running backend and Vue app with at least two dated submissions.
- Verify employee, team, full-period, 4-week, 8-week, and 12-week requests at desktop and mobile
  sizes.

## Documentation updates at implementation time

- Update `AGENTS.md` to make incremental cross-submission aggregation part of the supported
  lifecycle and remove it from the out-of-scope list.
- Rewrite the latest-snapshot sections of `docs/persistence.md`.
- Update `README.md` endpoint response examples and dashboard behavior.
- Update `docs/handover.md` with the two-submission acceptance procedure.
- Document correction precedence, idempotency, unsupported deletes, week anchoring, and the fact
  that filters always trigger backend recalculation.

## Completion definition

This work is complete when two separately submitted daily batches appear as one combined dashboard
dataset; corrections and retries cannot double-count evidence; every current frontend business
filter requests and receives a consistently recalculated backend result; and the regression suite,
frontend build, and live desktop/mobile checks all pass.
