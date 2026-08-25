# AGENTS.md — Employee Performance Tracking Agent (Backend)

This file is the primary development guide for the backend. Read it before writing code.
If something here conflicts with a request, mention the conflict and follow the request.

---

## 1. What this service does

A FastAPI backend that:

1. Ingests performance data from **CSV/Excel uploads** and, later, a **webhook**.
2. Hands it to an **AI agent that decides what is worth calculating**.
3. Gives that agent **tools** that do the actual arithmetic.

### The one rule that matters most

> **The AI decides *what* to calculate. Tools do the calculating.**

The agent interprets and orchestrates: read the data, decide which numbers matter, call tools
to compute them. Any number in a response should have come out of a Python tool, not out of
the model's own output.

The real shape of customer data has not been seen yet. Build for data that exists, not for
formats we imagine a customer might send.

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
    │   ├── agent.py          # POST /ask
    │   └── health.py         # GET /health
    ├── schemas/              # Pydantic request/response + internal models ONLY
    │   ├── agent.py          # AskRequest, AskResponse
    │   ├── performance.py    # canonical performance records and tool results
    │   └── uploads.py        # upload-inspection response models
    ├── services/             # all business logic lives here
    │   ├── agent.py          # PydanticAI agent + its tools
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

The agent explores that catalog progressively through data-access tools. It decides which
tables and columns matter for the user’s request, and may propose a mapping to canonical
performance concepts when that is useful. Python must validate any proposal before it becomes
a `PerformanceDataset` or feeds a named KPI calculator. Preserve source record IDs and
evidence links so results and alerts remain traceable.

Never put every row from every sheet into one model prompt. The agent should first inspect the
catalog, then request bounded samples, selected columns, or filtered rows. Python detects
mechanical issues such as blank columns and duplicate rows; the agent decides what is
analytically redundant. Neither the agent nor calculation tools receive raw pandas frames.

---

## 6. Calculations

Give the agent two kinds of tools. Data-access tools expose the upload safely and progressively:
`list_tables`, `describe_table`, `get_rows` with bounded columns/filters/limits, and
`profile_data` for types, missing values, blank columns, and duplicates. Calculation tools
perform arithmetic over explicitly selected data and return auditable results.

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
must not reduce compliance. Tools own all arithmetic, and every number returned must be
traceable to the tool call that produced it.

---

## 7. AI boundaries

Only the agent module may call a model. Nothing else, ever.

The agent **may**: inspect the data, decide what is worth calculating, call tools.
The agent **may not**: do arithmetic itself, or return a number it did not get from a tool.

The agent may interpret unfamiliar sheet and column names, but it must return a structured
mapping proposal with a confidence assessment. Python validates required fields, types,
duplicate mappings, and ID relationships before using that mapping. The agent may say that a
mapping is uncertain; it must not guess.

Enforce this structurally — typed tool arguments, a typed output shape — rather than by
asking nicely in the prompt. Report what the agent chose and why alongside the results;
free-form output is not an excuse for an unexplained response.

No API key → the service still starts, and endpoints needing the agent say so plainly.

The agent tools take request-scoped upload data as dependencies. Until the upload flow passes
that catalog into an agent run, they must report that no uploaded data is available rather than
fabricate a result.

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
| `POST` | `/api/v1/analyze` | accept and mechanically inspect a CSV/Excel upload; agent exploration is TODO |
| `POST` | `/api/v1/report` | explain what was chosen and why, alongside results **(TODO — not yet implemented)** |

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
