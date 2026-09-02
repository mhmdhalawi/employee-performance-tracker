# Persistence and dashboard flow

SQLite persistence is local to one company deployment. The default database is
`storage/tracker.sqlite3`; override it with `DATABASE_PATH`. Keep the database on the same
machine as the FastAPI process. The database file and its WAL sidecar files are ignored by Git.

## Request flow

`POST /api/v1/analyze-tables` remains the webhook/Postman endpoint. An unfiltered request follows
this sequence:

1. Pydantic validates the `{ "tables": [...] }` request.
2. The service creates a pending row in `submissions` containing the complete request JSON, its
   SHA-256 checksum, schema fingerprint, and table/row counts.
3. The existing bounded LLM mapping and deterministic Python calculation workflow runs.
4. In one SQLite transaction, the service stores the validated calculation plan in
   `mapping_plans`, stores the complete typed response in `analysis_runs`, and marks the
   submission completed.
5. If analysis fails, the request remains stored with `status = 'failed'` and a bounded error
   message. It never becomes the dashboard's latest completed submission.

Requests that include analysis query filters remain transient calculations and are not recorded
as new canonical submissions.

## Dashboard flow

`GET /api/v1/dashboard` returns the newest completed response snapshot. The response is validated
back into `AnalysisResponse` before it leaves the backend, and it receives a fresh process-local
insight context so `/api/v1/insights` continues to work after a server restart.

The endpoint accepts the existing `employee_id`, `team`, `start_date`, and `end_date` filters.
When any filter is present, the backend reloads the latest stored request and its validated
calculation plan, then reruns deterministic Python validation and KPI calculations. It does not
ask the mapping LLM to classify the schema again.

The Vue app currently hides the upload/sample entry screen with `SHOW_DATA_SOURCE_PAGE = false`.
After authentication it calls `GET /api/v1/dashboard`; it does not automatically send the bundled
sample request. Send a Postman request first, then load or refresh the frontend.

## Stored tables

- `submissions`: immutable request JSON and ingestion status.
- `mapping_plans`: the validated table classifications and calculator bindings, keyed by schema
  fingerprint.
- `analysis_runs`: the complete canonical dashboard response and its coverage/model metadata.

Migration `migrations/001_initial.sql` is applied automatically. SQLite uses WAL mode, foreign-key
validation, a five-second busy timeout, and one short-lived connection per operation.

## Daily submissions and history boundary

Every unfiltered webhook call is stored independently, so daily data is not lost. The current
dashboard intentionally reads only the latest completed submission. It does not merge multiple
submissions because the request contract does not yet say whether a daily payload is an
incremental batch or a full replacement snapshot. Automatically merging without that distinction
could double-count repeated records or retain corrected records incorrectly.

Before cross-submission monthly reporting is enabled, add an explicit submission mode or establish
one fixed deployment-wide rule. The next migration can then normalize source evidence by record ID
and occurrence date, supersede corrections deterministically, and calculate arbitrary historical
ranges across submissions.
