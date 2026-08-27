# AGENTS.md — Employee Performance Tracking Agent (Backend)

This file is the primary development guide for the backend. Read it before writing code.
If something here conflicts with a request, mention the conflict and follow the request.

---

## 1. What this service does

A FastAPI backend that:

1. Lets a user upload a **CSV or Excel workbook** and press Submit once.
2. Parses the upload into a request-scoped catalog without assigning business meaning.
3. Builds a bounded catalog synopsis for an **AI agent that selects relevant tables and
   proposes semantic mappings**.
4. Validates the agent's mappings, validates the mapped records, and performs all arithmetic
   deterministically in Python.
5. Returns structured employee results with employee ID/name when available, the three KPI
   scores, overall performance, limitations, and supporting evidence.

`POST /api/v1/analyze` owns that one-request workflow. `POST /api/v1/ask` is retained only as
a small LLM connectivity test; it does not receive or analyze uploaded data.

### The one rule that matters most

> **The AI decides *what* to calculate. Tools do the calculating.**

The agent interprets source semantics and proposes mappings. Python validates those mappings,
decides which deterministic calculators can run, and computes every number in the response.

The real shape of customer data has not been seen yet. Build for data that exists, not for
formats we imagine a customer might send.

### Benchmark workbook context

The development benchmark is `Cedar Employee Performance Agent — Complete Project
Dataset.xlsx`. Its `00_Start_Here` sheet defines the intended product and guardrails:

- Build and validate a Productivity, Compliance, and Quality dashboard through the seven-day
  delivery plan tracked in `docs/plan.md`.
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
- Python owns deterministic validation and arithmetic. The agent interprets mappings and
  explains tool results; it never invents scores.
- `Expected_KPI` is the authoritative numerical benchmark for Phase 3, and `QA_Test_Cases` is
  the minimum regression suite for Phase 6.

The workbook also states that missing quality reviews lower confidence and that an overall
result requires all three verified KPI scores. The current implementation gates overall
performance primarily on verified project evidence. Do not resolve this discrepancy by
assumption: compare the competing interpretations against `Expected_KPI` during Phase 3 and
document the rule that reproduces the benchmark.

Read `docs/benchmark.md` before work that changes KPI formulas, confidence, QA expectations,
or evidence-backed explanations. The workbook normally lives outside the repository and may
require the user to attach it or authorize its local path in a new session.

---

## 2. Stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.14 (`.python-version`) |
| Web | FastAPI (`fastapi[standard]`) |
| Deps / env | **uv** (never `pip install` into the venv) |
| Validation | Pydantic v2 + pydantic-settings |
| Tabular data | pandas (+ openpyxl for `.xlsx`) |
| LLM | `openai` SDK |
| Agent layer | PydanticAI (`pydantic-ai-slim[openai]`) |

**Not allowed without a strong, stated reason:** LangChain, a database/ORM, Celery/Redis,
Docker Compose stacks, auth systems.

---

## 3. Commands

```bash
uv sync                              # install/refresh deps from uv.lock
uv add <package>                     # add a dependency (updates pyproject + lock)
uvx library-skills --all             # discover/refresh AI skills bundled with installed dependencies

uv run fastapi dev app/main.py       # dev server, http://127.0.0.1:8000/docs
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

**The repo root *is* the backend**, and the application package is `app/` at the root — a
flat layout, not `src/`. The build backend is told this explicitly in `pyproject.toml`:

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
│   └── plan.md               # implementation phases and acceptance criteria
├── pyproject.toml            # deps + build config
├── .env.example
└── app/
    ├── main.py               # app, middleware, exception handlers, routers
    ├── api/                  # FastAPI routes — thin: parse, call one service, return
    │   ├── agent.py          # POST /ask and POST /analyze
    │   └── health.py         # GET /health
    ├── schemas/              # Pydantic request/response + internal models ONLY
    │   ├── agent.py          # AskRequest, AskResponse
    │   ├── performance.py    # canonical performance records and tool results
    │   └── uploads.py        # upload-inspection response models
    ├── services/             # all business logic lives here
    │   ├── agent.py          # PydanticAI mapping agent + analysis workflow
    │   ├── imports.py        # mechanical upload parsing and inspection
    │   ├── performance.py    # validation and deterministic KPI calculations
    │   └── uploads.py        # extension and size validation
    ├── core/                 # config, errors, clients, storage
    │   ├── config.py         # Settings (env-driven), get_settings()
    │   └── errors.py         # AppError hierarchy + FastAPI handler
    └── utils/                # small pure helpers (nothing here yet)
```

### Dependency direction

```
api  ->  services  ->  schemas / utils / core
```

`api/` may not import pandas, may not call OpenAI, and may not do arithmetic.
`services/` must not import FastAPI (`Request`, `UploadFile`, `HTTPException`, …) — services
take plain `bytes`/models and raise `AppError` subclasses. That keeps them reusable from the
future webhook path.

---

## 5. Data model

Analysis is per request. Python parses an upload into a request-scoped catalog of tables,
headers, inferred types, row counts, and raw records; it preserves the original file unchanged.
It does not decide what a table means merely from its sheet name.

Python reduces the catalog to bounded table metadata, inferred column profiles, duplicate
counts, and at most two sample rows per table. The agent uses that synopsis to decide which
tables and columns map to canonical performance concepts. Python must validate every proposal
before it becomes a `PerformanceDataset` or feeds a named KPI calculator. Preserve source
record IDs and evidence links so results and alerts remain traceable.

Never put every row from every sheet into a model prompt. The current mapping request contains
only the compact synopsis; the agent has no raw-row access tools. Python detects mechanical
issues such as blank columns and duplicate rows. Neither the agent nor calculation services
receive raw pandas frames.

### Analyze request lifecycle

The intended production lifecycle is:

```
upload -> validate/parse -> catalog -> agent table selection -> validated mappings
       -> canonical performance dataset -> Python KPI tools -> structured response
```

The compact synopsis is serialized into one structured mapping request. Python validates the
returned mappings and makes one targeted repair request only when structural validation
fails. Calculation services may process complete selected datasets in Python without sending
the source rows to the model.

**Current implementation boundary:** `/analyze` validates and parses the upload, gives the
request-scoped catalog to the agent for bounded inspection and semantic mapping, validates the
returned mappings in Python, builds the canonical dataset, runs deterministic source-data
validation, and calculates the three KPI scores. The response contains employee-specific
findings, a validation summary, unmatched/global findings, and KPI results; it does not return
the parsed source rows. Phase 2 validation is complete. Phase 3 should verify the existing
deterministic KPI engine against the workbook's `Expected_KPI` benchmark within 0.1.

---

## 6. Calculations

Python prepares a compact mapping synopsis containing table metadata, inferred column
profiles, duplicate counts, and at most two sample rows per table. The agent receives that
bounded synopsis in one structured-output request and returns selected tables plus semantic
mappings; it has no row-access or calculation tools in this path. Python validates the
returned mappings and makes one targeted repair request only when structural validation
fails. Validated mappings are cached in memory by a schema-only fingerprint so repeated
recognized layouts can skip the model while the server process remains running. Full record
validation and calculations run deterministically in Python without sending row-level output
back through the model.

Named domain calculators remain useful after Python validates an agent-proposed canonical
mapping: `validate_performance_data`, `calculate_performance_kpis`,
`get_performance_evidence`, and `compare_performance_periods`. The agent chooses whether a
named KPI, a generic safe aggregation, a trend comparison, or no calculation is appropriate.

The deterministic scorer uses Productivity (35%), Compliance (30%), and Quality (35%).
Productivity combines completion (60%) and time efficiency (40%); Compliance combines
attendance (50%), reports (35%), and leave compliance (15%); Quality combines accuracy (60%),
first-pass rate (25%), and rework (15%). Score only when verified project evidence meets the
employee's configured confidence threshold (70% by default); otherwise return
`Insufficient data`.

Exclude duplicate attendance before scoring. Approved annual and sick leave are neutral and
must not reduce compliance. Python owns all arithmetic, and every number returned must be
traceable to its supporting source records.

---

## 7. AI boundaries

Only the agent module may call a model. Nothing else, ever.

The agent **may**: interpret the bounded synopsis, select relevant tables, and propose mappings.
The agent **may not**: calculate or return KPI values, validate source records, or invent data.

The agent may interpret unfamiliar sheet and column names, but it must return a structured
mapping proposal with a confidence assessment. Python validates required fields, types,
duplicate mappings, and ID relationships before using that mapping. The agent may say that a
mapping is uncertain; it must not guess.

Enforce this structurally through a typed output shape and Python mapping validation rather
than asking nicely in the prompt. Mapping confidence communicates semantic uncertainty.

No API key → the service still starts, and endpoints needing the agent say so plainly.

The `/analyze` workflow constructs a request-scoped synopsis and passes it directly to the
mapping agent. The agent has no upload dependency or function tools. `/ask` remains a separate
plain connectivity test with no upload data.

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
| `POST` | `/api/v1/ask` | test whether the configured LLM can answer a plain prompt |
| `POST` | `/api/v1/analyze` | upload, map, validate, and return employee KPI results with findings |

---

## 9. Persistence

**TODO — nothing is persisted yet.** Every request is independent; nothing survives it.
Decide what actually needs storing (uploaded datasets? agent runs?) when something needs to
outlive a single request. Do not add a database without asking.

---

## 10. Style

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

---

## 11. Working agreements for coding tasks

1. Read the relevant service before editing; follow existing patterns over inventing new ones.
2. New logic goes into a **service**, not a route handler.
3. Reach for the simplest thing that satisfies the requirement; no speculative abstraction.
4. Touch only what the task needs — no drive-by refactors, no reformatting unrelated files.
5. Exercise the change against the running dev server before reporting done, and say plainly
   if anything fails.

---

## 12. Deliberately out of scope for now

Auth/multi-tenancy, database + migrations, background jobs, persisted historical data, PDF
export, streaming AI responses, rate limiting, tests.
