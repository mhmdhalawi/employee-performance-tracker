# Performance Tracking Agent

Employee performance analysis application with a FastAPI backend and a Vue 3 browser client.
It ingests CSV/Excel uploads or JSON tables, gives a bounded catalog synopsis to an AI agent
for KPI-family classification and calculator planning, validates the bound records, and calculates employee Productivity,
Compliance, and Quality scores deterministically in Python.

`POST /api/v1/analyze-tables` ingests incremental JSON upsert batches, retains their raw requests
and audit analyses, and publishes canonical evidence in SQLite. `GET /api/v1/dashboard` combines
all current canonical records and recalculates its employee, team, or period-filtered view in
Python.

The first KPI-bearing JSON submission must include employee and performance-target tables. Once
those foundations are canonical, later submissions may contain only new evidence tables. For
example, a quality-review-only batch can join stored employees by `employee_id`; it does not need
to repeat the employee or target tables.

The frontend lives in `web/` and uses Vue 3, TypeScript, Vite, Vue Router, Tailwind CSS v4,
and shadcn-vue. The backend remains authoritative for validation, KPI calculations, evidence
confidence, and trend calculations.

The browser client opens the aggregated persisted analysis and provides employee, team, and
backend-resolved reporting-period filters backed by API requests; backend-calculated summary KPIs;
sortable, paginated employee results with alert counts; weekly KPI trends; and a
responsive employee detail page containing traceable alerts and on-demand AI guidance. A
data-interpretation card and routed detail page group each contributing schema's KPI classifications,
confidence, selected calculators, and validated source-column bindings.
The dashboard uses `/`, with employee details at `/employees/:employeeId` and data interpretation
at `/data-interpretation`.
Employee Details can preview and download a two-page employee report. The dashboard can preview
and download a filtered team report and can directly download Productivity, Compliance, or
Quality summaries. PDFs are generated on demand in the browser from backend-calculated snapshots;
the application does not store generated report files.
The backend has no authentication/session layer. The frontend no longer includes upload or
sample-data entry cards; use Postman or a webhook to submit JSON tables, then refresh the frontend.

## Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Node.js
- pnpm 11

## Quick start

Install the backend and frontend dependencies from the repository root:

```bash
uv sync
cd web
pnpm install
cd ..
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to enable model-backed classification.
The service still starts without a key, and `/api/v1/health` reports whether AI is
configured.

Local SQLite defaults to `storage/tracker.sqlite3`. `.env.example` is only a template and never
updates an existing `.env` automatically. For Railway, attach a Volume at `/data` and set
`DATABASE_PATH=/data/tracker.sqlite3`; see [docs/persistence.md](docs/persistence.md).

Run the backend from the repository root in one terminal:

```bash
uv run fastapi dev app/main.py
```

The API documentation is available at http://127.0.0.1:8000/docs.

## Final verification

Run the complete deterministic unit, sanitized 30-employee benchmark, and upload API suite:

```bash
uv run python -m unittest discover -s tests -v
```

The suite runs without an API key. See `docs/handover.md` for fixture scope, benchmark
exceptions, and the recorded acceptance output.

Run the frontend in a second terminal:

```bash
cd web
pnpm dev
```

Open http://127.0.0.1:5173.

## Frontend commands

Run frontend commands from `web/`:

```bash
pnpm install                         # install dependencies
pnpm dev                             # start the Vite development server
pnpm build                           # type-check and build for production
pnpm preview                         # preview the production build locally
pnpm dlx shadcn-vue@latest add button # add a shadcn-vue component as source
```

Use pnpm rather than npm or yarn so `web/pnpm-lock.yaml` remains authoritative. Generated
folders such as `web/node_modules`, `web/dist`, and `.pnpm-store` must not be committed.

## Agent skills setup

After cloning the project, restore its coding-agent skills:

```bash
uv sync
npx skills install
uvx library-skills --all
```

`skills-lock.json` restores skills added from remote repositories. `uv.lock` pins Python
dependencies, and `library-skills` discovers skills bundled by those installed packages.

## Available endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness and whether AI is configured |
| `POST` | `/api/v1/ask` | Test the configured model with a plain prompt |
| `POST` | `/api/v1/analyze` | Upload, classify, validate, and analyze CSV/XLSX performance data |
| `POST` | `/api/v1/analyze-tables` | Ingest an incremental JSON batch and return a `201` submission receipt |
| `GET` | `/api/v1/dashboard` | Recalculate the combined canonical dashboard or a backend-filtered view |
| `POST` | `/api/v1/insights` | Generate optional guidance for one employee from the temporary validated analysis context |
| `POST` | `/api/v1/reports/employee/preview` | Build a deterministic employee report snapshot for browser PDF generation |

Employee report requests accept an `employee_id` plus either `period_weeks=4|8|12` or an explicit
inclusive `start_date`/`end_date` pair. The response uses the same canonical dashboard path and
confidence gate as the filtered UI and is marked `Cache-Control: no-store`. Team and KPI exports
reuse the current filtered dashboard response and therefore do not have separate report APIs.

Reports contain employee data, while this MVP has no authentication or authorization layer.
Protect a deployed instance with an approved external access gateway. The reports are intended
for coaching and manager review, not as the sole basis for employment decisions.

Send webhook retries with a stable deployment-wide idempotency key:

```http
POST /api/v1/analyze-tables
Idempotency-Key: payroll-export-2026-09-02
Content-Type: application/json
```

A successful synchronous ingestion returns `201 Created`:

```json
{
  "submission_id": "4d5c0d52-0000-4000-8000-000000000000",
  "status": "completed",
  "received_at": "2026-09-02T08:30:00Z",
  "coverage_start": "2026-09-01",
  "coverage_end": "2026-09-02"
}
```

Dashboard filters always trigger one backend recalculation. Use `period_weeks=4`, `8`, or `12`,
or explicit inclusive dates, but not both:

```http
GET /api/v1/dashboard?team=Operations&period_weeks=4
```

Mapping caches store only validated semantic bindings. A cache hit can avoid an LLM request, but
every accepted submission is still written to SQLite and every dashboard request still rebuilds,
filters, validates, and calculates the current canonical dataset in Python.

## Development guide

**Read [AGENTS.md](AGENTS.md) before writing code** — architecture, the AI boundary, and
conventions live there.
