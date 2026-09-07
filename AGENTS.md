# AGENTS.md — Employee Performance Tracking Agent

This file is the primary development guide for the FastAPI backend and Vue web app. Read it
before writing code.
If something here conflicts with a request, mention the conflict and follow the request.

Read `docs/design.md` before work that changes the frontend's visual design, Cedar branding,
logo usage, theme tokens, charts, sign-in/loading/error states, or browser-generated PDF
presentation. It records implemented direction alongside unresolved proposals; those proposals
do not by themselves authorize implementation. Read `docs/ux-guidelines.md` for shared component
ownership, filter state, navigation, and interaction behavior.

---

## 1. What this service does

The core product gives clients two supported ways to supply employee-performance data:

- **Upload a file:** send a CSV or Excel (`.xlsx`) file to `POST /api/v1/analyze`.
- **Send data directly:** submit JSON tables and rows to `POST /api/v1/analyze-tables`.

Both options run the shared classification, validation, and deterministic calculation workflow,
persist their submissions and canonical evidence in SQLite, and feed the same aggregated
dashboard. Clients can use either option or combine them; both use the same record-identity
and upsert rules. Preserve both ingestion options when evolving the product. The current Vue
dashboard has no upload or data-entry controls; these two options are available through the API.

A FastAPI backend that:

1. Accepts either a **CSV/Excel workbook** or JSON tables with their rows.
2. Builds a request-scoped catalog without assigning business meaning.
3. Builds a bounded catalog synopsis for an **AI agent that classifies tables by KPI family,
   selects approved calculators, and proposes calculator-specific field bindings**.
4. Validates the agent's plan and bound records, then performs all arithmetic
   deterministically in Python.
5. Persists file uploads and unfiltered JSON submissions, validated plans, audit responses,
   and canonical evidence in SQLite.
6. Returns structured employee results with employee ID/name when available, the three KPI
   scores, evidence confidence, gated overall performance and tier, a deterministic summary,
   limitations, and supporting evidence.

`POST /api/v1/analyze` owns the upload workflow, while `POST /api/v1/analyze-tables` accepts
JSON tables and runs the same catalog analysis, and `POST /api/v1/analyze-tables-preview`
runs that analysis without touching persistence.

### The one rule that matters most

> **The AI decides *what* to calculate. Tools do the calculating.**

The agent interprets source semantics and proposes a classification and calculation plan.
Python validates that plan, decides which deterministic calculators can run, and computes every
number in the response.

The real shape of customer data has not been seen yet. Build for data that exists, not for
formats we imagine a customer might send.

### Benchmark workbook context

The development benchmark is `Cedar Employee Performance Agent — Complete Project
Dataset.xlsx`. Its `00_Start_Here` sheet defines the intended product and guardrails:

- Build and validate a Productivity, Compliance, and Quality dashboard against the benchmark
  and acceptance criteria preserved in `docs/benchmark.md`.
- The benchmark contains 30 employees over the 12-week period from 2026-05-25 through
  2026-08-22.
- Productivity is 35%, Compliance is 30%, and Quality is 35% of the overall result.
- Below 70% evidence confidence, return `Insufficient data`; do not present a misleading low
  score.
- Productivity evidence comes from completed projects and actual hours. Compliance evidence
  comes from attendance, reports, and leave. Quality evidence comes from accuracy,
  first-pass approval, and rework.
- Approved leave is neutral, duplicates are excluded before calculation, and alerts cite
  supporting record IDs or evidence links.
- Python owns deterministic validation and arithmetic. The agent interprets classifications and calculator bindings and
  explains tool results; it never invents scores.
- `Expected_KPI` is the authoritative numerical benchmark for Phase 3, and `QA_Test_Cases` is
  the minimum regression suite for Phase 6.

Employee data confidence is the lowest required-evidence coverage across projects, attendance
check-outs, submitted reports, and quality reviews. Missing required evidence lowers employee
confidence and never becomes zero performance.
Component KPI calculations remain visible below the threshold for auditability, while the
overall score and performance tier are withheld and the status is `Insufficient data`.

QA-01 and QA-10 conflict for EMP-027 and EMP-029: QA-01 requires duplicate attendance
exclusion, while a controlled API parity run confirmed that their `Expected_KPI` Compliance
values include the duplicate rows. Production preserves QA-01. Treat those two values as a
documented benchmark exception until the workbook owner corrects or confirms them.

Read `docs/benchmark.md` before work that changes KPI formulas, confidence, QA expectations,
or evidence-backed explanations. The workbook normally lives outside the repository and may
require the user to attach it or authorize its local path in a new session.

---

## 2. Stack

| Concern | Choice |
| --- | --- |
| Backend language | Python 3.14 (`.python-version`) |
| Backend web | FastAPI (`fastapi[standard]`) |
| Backend deps / env | **uv** (never `pip install` into the venv) |
| Validation | Pydantic v2 + pydantic-settings |
| Tabular data | pandas (+ openpyxl for `.xlsx`) |
| LLM | `openai` SDK |
| Agent layer | PydanticAI (`pydantic-ai-slim[openai]`) |
| Frontend | Vue 3 + TypeScript + Vite + Vue Router (`web/`) |
| Frontend deps | **pnpm** (never npm or yarn) |
| Frontend styling | Tailwind CSS v4 + shadcn-vue (Nova, neutral) |
| Persistence | SQLite via the Python standard library; numbered SQL migrations |

**Not allowed without a strong, stated reason:** LangChain, an ORM or second database layer,
Celery/Redis, Docker Compose stacks, auth systems.

---

## 3. Commands

```bash
uv sync                              # install/refresh deps from uv.lock
uv add <package>                     # add a dependency (updates pyproject + lock)
uvx library-skills --all             # discover/refresh AI skills bundled with installed dependencies

uv run fastapi dev app/main.py       # dev server, http://127.0.0.1:8000/docs
uv run python -m unittest discover -s tests -v
                                     # deterministic service regression suite
uv run ruff check app tests          # lint gate for the style rules in section 10
uv run ruff check app tests --fix    # apply the mechanical fixes (import order, __all__)

cd web
pnpm install                         # install/refresh deps from pnpm-lock.yaml
pnpm dev                             # frontend dev server, http://127.0.0.1:5173
pnpm build                           # type-check and create the production build
pnpm dlx shadcn-vue@latest add <component>  # add a shadcn-vue component as source
```

Run `uvx library-skills --all` after adding or updating dependencies. It only adds skills
for packages that bundle an official agent skill.

### Agent skills setup

On a fresh clone, restore project skills after installing dependencies:

```bash
uv sync
npx skills install
uvx library-skills --all
```

`skills-lock.json` pins skills added from remote repositories. `uv.lock` pins Python
dependencies, and `library-skills` discovers any skills bundled by those dependencies.

Copy `.env.example` → `.env` and set `OPENAI_API_KEY` to enable the agent.

---

## 4. Layout

The backend remains at the repository root, and the application package is `app/` — a flat
Python layout, not `src/`. The independently managed browser client lives in `web/`. The
Python build backend is told about the flat backend layout explicitly in `pyproject.toml`:

```toml
[tool.uv.build-backend]
module-name = "app"
module-root = ""
```

The distribution is still named `tracker` (the project name); the importable package is `app`.
So every internal import reads `from app.services… import`.

```
tracker/
├── AGENTS.md
├── docs/
│   ├── benchmark.md          # stable workbook context and confirmed benchmark exceptions
│   ├── data-dictionary.md    # normalized deterministic calculator fields and formulas
│   ├── design.md             # Cedar visual direction, accessibility rules, and open decisions
│   ├── ux-guidelines.md        # shared frontend components, state, and interaction behavior
│   ├── handover.md           # reproducible acceptance-test handover
│   └── persistence.md        # SQLite, dashboard, filtering, and Railway deployment flow
├── migrations/
│   ├── 001_initial.sql       # submissions, mapping plans, and analysis snapshots
│   └── 002_aggregated_evidence.sql # idempotency, plan snapshots, canonical current state
├── storage/                  # ignored local SQLite files; only .gitkeep is committed
├── pyproject.toml            # deps + build config
├── uv.lock                   # Python dependency lock
├── .env.example
├── app/
│   ├── main.py               # app, middleware, exception handlers, routers
│   ├── api/                  # FastAPI routes — thin: parse, call one service, return
│   │   ├── agent.py          # analysis and persisted dashboard endpoints
│   │   ├── health.py         # GET /health
│   │   └── reports.py        # deterministic employee report-preview endpoint
│   ├── schemas/              # Pydantic request/response + internal models ONLY
│   │   ├── calculators.py    # THE approved-calculator registry (see below)
│   │   ├── health.py         # HealthResponse
│   │   ├── performance.py    # generic calculator evidence records and tool results
│   │   ├── reports.py        # renderer-ready employee report contract
│   │   ├── tables.py         # JSON table request models
│   │   └── uploads.py        # catalog, upload, and analysis response models
│   ├── services/             # all business logic lives here
│   │   ├── agent/            # model-facing ONLY: prompts, model, context, planning, cache,
│   │   │                     #   workflow. Nothing else in the codebase may call a model.
│   │   ├── aggregation.py    # canonical merge, serialization, and materialization
│   │   ├── analysis.py       # deterministic AnalysisResponse assembly (no model access)
│   │   ├── catalog.py        # catalog profiling and plan/binding validation
│   │   ├── datasets.py       # binds a validated plan to typed evidence records
│   │   ├── filters.py        # shared reporting-period filter validation
│   │   ├── imports.py        # mechanical upload parsing and inspection
│   │   ├── performance/      # validation, scoring, evidence, metrics, and trends
│   │   ├── reports.py        # employee snapshot built from filtered dashboard results
│   │   ├── submissions/      # JSON/upload ingestion and persisted dashboard reads
│   │   ├── tables.py         # mechanical JSON table-to-catalog conversion
│   │   └── uploads.py        # extension and size validation
│   ├── core/                 # cross-cutting configuration and application errors
│   │   ├── config.py         # Settings (env-driven), get_settings()
│   │   └── errors.py         # AppError hierarchy + FastAPI handler
│   ├── database/             # SQLite connection, models, reads, and atomic publication
│   └── utils/                # small pure helpers: dates.py, numbers.py
├── tests/
│   ├── benchmark_fixture.py  # sanitized 30-employee workbook and plan builder
│   ├── test_api_integration.py # uploads, JSON persistence, dashboard, and filter API tests
│   ├── test_benchmark.py     # sanitized 30-employee benchmark parity
│   ├── test_catalog.py       # catalog profiling, plan validation, and repair merging
│   ├── test_performance.py   # generic-evidence KPI and validation regressions
│   └── test_tables.py        # JSON table request conversion
└── web/                      # Vue 3 browser client
    ├── components.json       # shadcn-vue project configuration
    ├── package.json          # frontend scripts and dependencies
    ├── pnpm-lock.yaml        # frontend dependency lock
    ├── vite.config.ts        # Vite, Tailwind, and @ alias configuration
    └── src/
        ├── components/       # app and shadcn-vue components
        ├── composables/       # shared Vue behavior, including dashboard navigation
        ├── lib/              # shared helpers and browser PDF generators
        ├── router/           # Vue Router configuration and route metadata
        ├── types/reports.ts  # employee report API contract
        ├── views/            # route-level employee and data-interpretation views
        ├── App.vue
        ├── main.ts
        └── style.css         # Tailwind import and global theme tokens
```

### The calculator registry

`app/schemas/calculators.py` is the single source of truth for every approved calculator. One
`CalculatorSpec` per calculator carries its name, Pydantic input model, KPI family, dataset
collection, canonical record type, identity field, and period fields. Everything downstream is
derived from that one tuple:

| Consumer | What it derives |
| --- | --- |
| `services/catalog.py` | the calculator contract sent to the agent, and binding validation |
| `services/datasets.py` | which model and collection a validated binding produces |
| `services/aggregation.py` | canonical record writes, batch identity, and materialization |
| `schemas/uploads.py` | the `CalculatorName` literal the agent must return |

**Adding or changing a calculator is one edit in `calculators.py`.** Do not reintroduce a
per-module lookup table; a module-level check fails at import if `CalculatorName` and the
registry ever disagree. Registry order is significant — it fixes the order of the contract sent
to the model and of canonical record writes.

### Dependency direction

```
api  ->  services  ->  schemas / utils / core / database
```

`api/` may not import pandas, may not call OpenAI, and may not do arithmetic.
`services/` must not import FastAPI (`Request`, `UploadFile`, `HTTPException`, …) — services
take plain `bytes`/models and raise `AppError` subclasses. That keeps them reusable from the
future webhook path.

### Frontend architecture

The `web/` app is a separate Vite application in the same repository. It consumes the
FastAPI `/api/v1` contract and must not import Python modules. Keep uploads, filters, view
state, and presentation logic in Vue; keep source validation, KPI formulas, evidence
confidence, trend calculation, and all other business arithmetic in Python.
Employee, team, and reporting-period selections request filtered results from the backend.
Vue Router owns browser navigation. The dashboard is served at `/`, employee details at
`/employees/:employeeId`, and data interpretation at `/data-interpretation`; `/dashboard` and
the previous root query-string detail URLs remain compatibility redirects.

Use pnpm exclusively within `web/`. Do not commit `node_modules/`, `dist/`, `.pnpm-store/`,
or other generated caches. The frontend may retain one structured analysis in browser memory,
but persisted dashboard data comes from the FastAPI API and authoritative KPI values remain
calculated in Python.

Use the configured `@/` alias for imports from `web/src`. Prefer existing shadcn-vue
components over custom equivalents and add them through
`pnpm dlx shadcn-vue@latest add <component>`. Before using or changing a shadcn-vue
component, inspect its current CLI documentation and the installed component source.

Use Tailwind semantic theme tokens such as `bg-background` and `text-muted-foreground`.
Use utility classes primarily for layout, prefer `gap-*` over `space-x-*`/`space-y-*`, use
`size-*` when width and height match, and use `cn()` for conditional classes. Preserve the
accessibility composition required by shadcn-vue, including titles for dialogs/sheets and
fallbacks for avatars.

### Report architecture

Reports are transient, manager-reviewed exports generated in the browser with `pdfmake`; the
backend does not render or store PDF files. Employee Details requests a typed, renderer-ready
snapshot from `POST /api/v1/reports/employee/preview`, previews that exact snapshot, and passes it
unchanged to `web/src/lib/employee-report-pdf.ts`. The report service obtains its values by calling
the same canonical dashboard materialization and filter path as `/dashboard`, including an
optional prior comparable period. It filters clickable evidence links to absolute `https` URLs
and returns `Cache-Control: no-store`; an unknown or non-renderable employee returns the typed
`employee_report_not_found` error.

Team and KPI summary exports do not have separate backend endpoints. The dashboard passes its
current filtered `DashboardResponse` directly to `web/src/lib/dashboard-report-pdf.ts`. The team
preview and all downloaded reports must preserve backend-provided scores, trends, confidence,
withheld overall results, resolved dates, and employee scope without browser-side KPI arithmetic.
Every PDF includes a manager-review notice. Report filenames are sanitized, PDF dependencies are
loaded only when an export is requested, object URLs are revoked after download, and generated
files are not retained by the application.

The implemented report family comprises a two-page portrait employee report, a landscape team
summary, and landscape Productivity, Compliance, and Quality summaries. Saved/history reports,
scheduled delivery, a data-quality report, server-side rendering, and authorization remain
unimplemented. Because reports contain employee data and the backend has no authorization layer,
protect any deployed instance with an approved external access gateway.

Backend integration tests cover employee-preview/dashboard parity, insufficient-data gating, and
unknown employees. The TypeScript production build verifies the browser generators compile, but
there is no automated PDF layout regression suite. For renderer changes, download scored and
insufficient-data examples and visually inspect every page, including long names, findings,
tables, wrapping, page breaks, and sanitized filenames.

---

## 5. Data model

Analysis is per request. Python parses an upload into a request-scoped catalog of tables,
headers, inferred types, row counts, and raw records; it preserves the original file unchanged.
It does not decide what a table means merely from its sheet name.

Python reduces the catalog to bounded table metadata, row counts, column names and inferred
types, plus compact mechanically derived signals such as identifier-shaped names, sparsity,
cardinality, and numeric ranges. The initial mapping prompt contains neither complete sample
rows nor exact missing, unique, or duplicate counts. The agent uses that synopsis to decide which
tables support KPI families and which approved calculators their columns can feed. Python must
validate every proposal before it becomes a `PerformanceEvidenceDataset` or feeds a named KPI
calculator. Preserve source
record IDs and evidence links so results and alerts remain traceable.

Never put every row from every sheet into a model prompt. The current planning request contains
only the compact synopsis; the agent has no raw-row access tools. Python detects mechanical
issues such as blank columns and duplicate rows. Neither the agent nor calculation services
receive raw pandas frames.

### Analyze request lifecycle

The intended production lifecycle is:

```
upload -> validate/parse -> catalog -> agent KPI classification -> validated calculation plan
       -> generic evidence dataset -> Python KPI tools -> structured response
       -> optional on-demand AI explanation -> Python citation validation
```

The compact synopsis is serialized into one structured classification and calculator-planning
request. Python validates the returned classifications and bindings and makes one targeted
repair request only when structural validation fails. That repair receives only the affected
table profiles plus at most three distinct low-cardinality examples for safe, non-sensitive text
columns; it returns only corrected classifications, which Python merges without allowing valid
classifications to be overwritten. Calculation services may process complete selected datasets
in Python without sending the source rows to the model.

**Current implementation boundary:** `/analyze` persists uploads and publishes canonical evidence while returning its existing analysis response.
`/analyze-tables` treats each validated JSON request as an incremental upsert batch, preserves its
raw request and audit analysis, publishes canonical current-state evidence, and returns a typed
submission receipt. `/dashboard` combines canonical records from all contributing completed
submissions and recalculates every filtered view. Both analysis paths build the
generic evidence dataset, run deterministic source-data validation, and calculate KPI scores,
evidence confidence, gated overall scores, and tiers.
The first submission through either ingestion option that invokes KPI calculators must provide both employee and performance-
target foundations. Later partial submissions may contain only new KPI evidence: plan validation
can satisfy those two foundation requirements from completed canonical `employee` and
`performance_target` records already in SQLite. The combined dashboard still reports unknown
employee IDs, missing targets, and missing evidence deterministically.
The response contains employee-specific findings, supporting record IDs, a validation
summary, unmatched/global findings, KPI results, applied filters, deterministic weekly trends,
and a deterministic summary derived from the final results; it does not return parsed source
rows. The Vue client presents employee results with alert counts and sorting, KPI trends,
and a responsive routed employee detail page containing traceable alerts.
Employee Details also previews and downloads an employee PDF for the active period. The main
dashboard previews a team report and downloads team or per-KPI PDF summaries from its current
filtered response.
The dashboard also exposes a compact data-interpretation summary and routed detail page for table
classifications, confidence, approved calculator invocations, and field bindings grouped by
contributing schema. The Vue app opens the aggregated persisted dashboard directly; the upload
and sample-data entry cards have been removed from the frontend. Week presets are resolved by
the backend against the latest business date in canonical evidence.
The incremental multi-submission aggregation plan is implemented, with the documented
EMP-027/EMP-029 benchmark exception described in `docs/benchmark.md`.

---

## 6. Calculations

Python prepares a compact classification synopsis containing table metadata, row counts, column
names and inferred types, and mechanically derived semantic signals without complete sample
rows or exact profile counts. The agent receives that bounded synopsis in one structured-output
request and returns selected tables plus semantic
calculator invocations and bindings; it has no row-access or calculation tools in this path.
Python validates the returned plan and makes one targeted repair request with safe per-column
examples only when structural validation fails. Validated plans are cached in memory by a
schema-only fingerprint so repeated recognized layouts can skip the model while the server
process remains running. Canonical JSON ingestions store both the reusable plan and an immutable
per-submission plan snapshot in SQLite. Aggregated `/dashboard` reads materialize validated
canonical evidence directly and never call the mapping model. Full record
validation and calculations run deterministically in Python. A bounded on-demand explanation
request may receive one employee's result status and validated findings, but never raw source
rows or complete KPI calculation inputs.

A mapping-cache hit skips only semantic classification. It never skips submission persistence,
canonical upserts, record validation, duplicate handling, or deterministic KPI calculation.
Without an idempotency key, identical requests are separate audited submissions even when they
reuse one mapping plan. A smaller unseen schema may also be faster on a cache miss because its
catalog synopsis, token usage, binding work, and canonical write set are smaller.

After Python validates an agent-proposed classification and calculator plan, the deterministic
service uses `validate_dataset`, `calculate_kpis`, `calculate_weekly_kpi_trends`, and
`build_performance_alerts`. The planning agent selects only approved calculators; it does not
choose formulas or execute calculations.

The deterministic scorer uses Productivity (35%), Compliance (30%), and Quality (35%).
Productivity combines completion (60%) and time efficiency (40%); Compliance combines
attendance (50%), reports (35%), and leave compliance (15%); Quality combines accuracy (60%),
first-pass rate (25%), and rework (15%). Employee data confidence is the lowest required-
evidence coverage across project evidence, attendance check-outs, submitted-report evidence,
and quality-review evidence.
When confidence is below the employee's configured threshold (70% by default), retain the
component KPI calculations for traceability but return `Insufficient data` with no overall
score or performance tier.

Exclude duplicate attendance before scoring. Approved annual and sick leave are neutral and
must not reduce compliance. Python owns all arithmetic, and every number returned must be
traceable to its supporting source records.

---

## 7. AI boundaries

Only the agent module may call a model. Nothing else, ever.

The planning agent **may** interpret the bounded synopsis, classify tables by KPI family, select
approved calculators, and propose field bindings. The agent **may not** calculate or
alter KPI values, validate source records, invent data or causes, or make high-impact
employment recommendations.

The agent may interpret unfamiliar sheet and column names, but it must return a structured
calculation plan with a confidence assessment. Python validates required fields, types,
duplicate bindings, and ID relationships before using that plan. The agent may say that a
classification is uncertain; it must not guess.

Enforce this structurally through a typed output shape and Python plan validation rather
than asking nicely in the prompt. Classification confidence communicates semantic uncertainty.

No API key → the service still starts, and endpoints needing the agent say so plainly.

The `/analyze` and `/analyze-tables` workflows construct a request-scoped synopsis when no valid
mapping plan is cached. The planning agent has no upload dependency or function tools.

---

## 8. API conventions

- Prefix: `/api/v1`. Routers are thin: parse → call one service → return a Pydantic model.
- Always declare `response_model`. Response models live in `schemas/`, never inline dicts.
- Never `raise HTTPException` from a service. Raise an `AppError` subclass from
  `core/errors.py`; the registered handlers convert it to a consistent `ErrorResponse`
  (`{"error": {"code", "message"}}`).
- Validation failures inside a *file* are **not** HTTP errors: a file with 3 bad rows out of
  100 returns `200` with those rows listed. Only an unusable file (wrong type, unparseable)
  is a `4xx`.
- Uploads: enforce an extension allowlist and a size limit before parsing.

Current endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | liveness + whether AI is configured |
| `POST` | `/api/v1/analyze` | upload, classify, validate, and return employee KPI results with findings |
| `POST` | `/api/v1/analyze-tables` | ingest an incremental JSON upsert batch and return a `201` receipt |
| `POST` | `/api/v1/analyze-tables-preview` | analyze a complete JSON dataset without persistence and return the adjusted response with LLM usage/timing |
| `GET` | `/api/v1/dashboard` | recalculate the aggregated canonical dashboard with optional filters |
| `POST` | `/api/v1/reports/employee/preview` | return a deterministic employee report snapshot for browser PDF generation |

---

## 9. Persistence

Unfiltered JSON submissions sent to `/analyze-tables` are durably stored in local SQLite. The
database keeps every complete request, an immutable calculation-plan snapshot, the audit
`AnalysisResponse`, and one current canonical version per `(record_type, record_id)`.
`/dashboard` materializes those canonical records into one `PerformanceEvidenceDataset` and
recalculates with deterministic Python calculators. Later records upsert earlier identities;
omission never deletes a record, and tombstones are not supported.
Partial KPI batches may reuse canonical employees and performance targets from earlier completed
submissions; they do not need to repeat those tables. This allowance applies only when both
foundation record types actually exist in current canonical state. It does not weaken employee-ID,
target, or evidence validation in the aggregated dashboard.

The default path is `storage/tracker.sqlite3`, configurable with `DATABASE_PATH`. Keep SQLite on
local disk. Railway production requires a Volume mounted at `/data` and
`DATABASE_PATH=/data/tracker.sqlite3`; a Railway variable alone does not provide persistence.
Migrations live in `migrations/`, and database/WAL files must remain ignored by Git. An optional
deployment-wide `Idempotency-Key` prevents whole-request replays. Overlapping batches remain safe
because stable record identities are atomic SQLite upserts. Source versions or source update
timestamps take precedence, with completion time used only when neither is provided. See
`docs/persistence.md` for the full request lifecycle and Railway setup.

Uploads through `/analyze` persist the original bytes as base64 and the parsed catalog in SQLite, plus the unfiltered audit analysis, validated plan, and canonical evidence. Response filters never limit publication. Report previews are calculated on demand from canonical state; neither preview payloads
nor browser-generated PDFs are persisted.

---

## 10. Style

### Backend

- **No module-level docstrings or header comment blocks.** Files start directly with their
  first import or statement — no summary of what the file contains at the top. Architectural
  context belongs in this file, not repeated across source headers.
- Full type hints; modern syntax (`str | None`, `list[X]`, `dict[str, float]`).
- `snake_case` functions, `PascalCase` models.
- Docstrings on public *functions* are fine and wanted: what it does, what it raises. Explain
  *why* in inline comments, not *what*.
- Small pure functions in `utils/`; keep pandas usage in one place so the rest of the codebase
  deals in plain Pydantic models.
- No `print` in library code.
- A leading underscore means *module*-private. If another module imports it, it should not have
  one; import the sibling module (`from app.services.performance import metrics`) when the
  qualified call reads better or the bare name would shadow a local.
- `uv run ruff check app tests` enforces the mechanical part of these rules (import order,
  unused names, modern syntax, no `print`). Keep it clean; it is not run automatically.

### Frontend

- Use Vue Single-File Components with `<script setup lang="ts">` and fully typed props,
  emits, API data, and composables.
- Keep page-level orchestration in views/components and extract reusable stateful behaviour
  into composables. Do not put backend business rules into components.
- Use shadcn-vue components and variants before creating custom styled controls. Use Lucide
  icons through the icon package configured by `components.json`.
- Cover loading, empty, API-error, and `Insufficient data` states explicitly. Never turn a
  missing overall score into zero or infer a performance tier in the browser.

---

## 11. Working agreements for coding tasks

1. Read the relevant service before editing; follow existing patterns over inventing new ones.
2. New logic goes into a **service**, not a route handler.
3. Reach for the simplest thing that satisfies the requirement; no speculative abstraction.
4. Touch only what the task needs — no drive-by refactors, no reformatting unrelated files.
5. Exercise the change against the running dev server before reporting done, and say plainly
   if anything fails.
6. For frontend changes, also run `pnpm build` from `web/` and inspect the rendered app in a
   browser at the relevant desktop and mobile sizes.

---

## 12. Deliberately out of scope for now

Backend authentication/multi-tenancy, background jobs, tombstone/delete events, authoritative
period snapshots, server-side PDF rendering, streaming AI responses, and rate limiting.
