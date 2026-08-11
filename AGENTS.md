# AGENTS.md — Employee Performance Tracking Agent (Backend)

This file is the primary development guide for the backend. Read it before writing code.
If something here conflicts with a request, mention the conflict and follow the request.

---

## 1. What this service does

A FastAPI backend that:

1. Ingests employee performance data from **CSV/Excel uploads** (webhook ingestion later).
2. **Validates** and **normalizes** heterogeneous customer/role-specific formats into one
   internal representation.
3. **Deterministically calculates** three KPI families: **Productivity**, **Quality**,
   **Compliance**.
4. Exposes structured results for a **Vue dashboard**.
5. Optionally uses **OpenAI GPT** to *explain* already-calculated results as a written report.

### The one rule that matters most

> **KPI scores are computed by Python. The AI never produces a score.**

The AI has exactly two jobs, and neither is arithmetic:

1. **Interpretation** — deciding what an unrecognized spreadsheet column *means*
   (`services/mapping_agent.py`).
2. **Explanation** — writing prose about scores that already exist (`services/ai_report.py`).

Everything numeric happens in `services/kpi_engine.py`. If you ever find yourself asking the
model for a number that lands in a `score` field, stop.

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
| Agent layer | PydanticAI (`pydantic-ai-slim[openai]`) — column-mapping agent only |

**Not allowed without a strong, stated reason:** LangChain, a database/ORM, Celery/Redis,
Docker Compose stacks, auth systems. This is a 1–2 week MVP.

---

## 3. Commands

```bash
uv sync                              # install/refresh deps from uv.lock
uv add <package>                     # add a dependency (updates pyproject + lock)
uv add --dev <package>               # dev-only dependency

uv run fastapi dev app/main.py       # dev server, http://127.0.0.1:8000/docs
uv run tracker                       # same app via the console script
```

Copy `.env.example` → `.env` and set `OPENAI_API_KEY` to enable real AI reports.
Without a key the service still runs — `ai_report.py` falls back to a deterministic
template summary, so every endpoint works offline.

---

## 4. Layout

**The repo root *is* the backend**, and the application package is `app/` at the root — a
flat layout, not `src/`. The build backend is told this explicitly in `pyproject.toml`:

```toml
[tool.uv.build-backend]
module-name = "app"
module-root = ""
```

The distribution is still named `tracker` (that's the project name and the console script);
the importable package is `app`. So every internal import reads `from app.services… import`.

```
tracker/
├── AGENTS.md
├── pyproject.toml            # deps + build config
├── .env.example
├── app/
│   ├── main.py               # create_app(), middleware, exception handlers, run()
│   ├── api/
│   │   ├── router.py         # aggregates routers under /api/v1
│   │   ├── upload.py         # POST /uploads  (file -> normalize -> KPI)
│   │   ├── reports.py        # GET  /batches/... , POST /reports
│   │   └── health.py
│   ├── schemas/              # Pydantic request/response + internal models ONLY
│   │   ├── common.py         # NormalizedRecord, RowIssue, ErrorResponse
│   │   ├── upload.py
│   │   ├── mapping.py        # ColumnPreview, AgentMappingProposal, ResolvedMapping
│   │   ├── kpi.py            # KpiComponent, KpiFamilyScore, EmployeeKpiResult, BatchResult
│   │   └── report.py
│   ├── services/             # all business logic lives here
│   │   ├── file_processor.py # bytes -> DataFrame -> NormalizedRecord[] + issues + previews
│   │   ├── profiles.py       # per-role column aliases + KPI metric definitions (data, not code)
│   │   ├── mapping_agent.py  # PydanticAI agent: unknown columns -> canonical metrics
│   │   ├── ingestion.py      # orchestration: parse -> resolve mapping -> normalize -> score
│   │   ├── kpi_engine.py     # deterministic scoring, fully traceable
│   │   └── ai_report.py      # prompt building + OpenAI call + offline fallback
│   ├── core/
│   │   ├── config.py         # Settings (env-driven), get_settings()
│   │   ├── errors.py         # AppError hierarchy + FastAPI handlers
│   │   ├── openai_client.py  # cached AsyncOpenAI factory (returns None w/o key)
│   │   └── store.py          # in-memory batch store (MVP persistence)
│   └── utils/
│       └── numbers.py        # safe_div, clamp, round_score, coerce_float
```

### Dependency direction

```
api  ->  services  ->  schemas / utils / core
```

`api/` may not import pandas, may not call OpenAI, and may not do arithmetic on metrics.
`services/` must not import FastAPI (`Request`, `UploadFile`, `HTTPException`, …) — services
take plain `bytes`/models and raise `AppError` subclasses. That keeps them reusable from the
future webhook path.

---

## 5. Data model

### Normalized representation

Every input format collapses to `schemas/common.py::NormalizedRecord`:

```python
employee_id: str
employee_name: str | None
profile: str                  # role profile key, e.g. "support" | "developer"
period: str | None
metrics: dict[str, float]     # canonical metric name -> numeric value
source_row: int               # 1-based row number in the uploaded file
raw: dict[str, Any]           # original row, kept for traceability
```

`metrics` keys are **canonical names** (`tickets_resolved`, `cycle_time_days`, …) — never raw
header text. Mapping from messy headers to canonical names happens in `profiles.py` via
`aliases`, and nowhere else.

Column → canonical name resolution has two paths, selected by the `mapping_mode` form field:

| Mode | Behavior |
| --- | --- |
| `aliases` | Declared alias tables only. Fully deterministic, no model call, no token cost. |
| `hybrid` *(default)* | Aliases first; the agent is asked **only** about leftover columns. Skips the model entirely when nothing is left over. |
| `ai` | Every column goes to the agent; alias tables are not consulted. |

Both AI modes silently degrade to `aliases` when no model is configured, and the mode actually
used comes back in the response — so a caller always knows whether a model was involved.

### Role profiles

`services/profiles.py` is intentionally **declarative data**. A profile declares:

- `aliases`: canonical metric name → accepted header spellings (lowercased, normalized).
- `metrics`: per metric — `family`, `direction` (`higher_better` / `lower_better`), `target`,
  `weight`, `unit`, `description`.

Adding a role or a customer-specific format should require **only** a new entry there. If it
requires touching `kpi_engine.py`, the abstraction is wrong — fix the abstraction.

---

## 6. KPI contract

Scoring lives in `services/kpi_engine.py` and obeys these rules:

1. **Deterministic.** Same records + same mapping → same output. No randomness, no clock, no
   network, no LLM inside the engine. Note the precise claim: when the mapping agent is used,
   *which column feeds a metric* may vary between runs, but the scoring of a given mapping
   never does. That is why `resolved_mappings` is part of the upload response — it is the
   audit trail for the one non-deterministic input.
2. **0–100 per family**, rounded to 2 decimals. `overall` is the weighted mean of the
   available families.
3. **Normalization** (in `utils/numbers.py`, documented there):
   - `higher_better`: `clamp(value / target, 0, 1) * 100`
   - `lower_better`: `clamp(target / value, 0, 1) * 100` (`value <= 0` → 100)
4. **Explainability is mandatory.** Every family score carries `components: list[KpiComponent]`,
   each holding `metric`, `raw_value`, `target`, `direction`, `normalized_score`, `weight`,
   `contribution`, `source_field`. A score you cannot trace back to source columns is a bug.
5. **Missing data is never invented.** A missing metric becomes a component with
   `available=False`, is excluded from the weighted mean, and the remaining weights are
   renormalized. If a family has no available metrics, its `score` is `None` with a
   `reason` — do **not** emit `0.0`.
6. Metric values are floats. Non-numeric cells are reported as `RowIssue`, not coerced to 0.

When changing a formula, update the docstring and the `AGENTS.md` rule above if the rule itself
changed, in the same commit.

---

## 7. AI boundaries

Two modules may call a model: `services/mapping_agent.py` and `services/ai_report.py`.
Nothing else, ever.

### 7a. The mapping agent (PydanticAI)

Handles the "customer sent columns nobody anticipated" problem. It decides **which column
feeds which canonical metric**, then the ordinary deterministic engine scores it.

The agent may: choose a role profile, map a column to an **existing** canonical metric,
identify the employee-id/name/period columns, and call tools to inspect and test-score sample
values.

The agent may not: invent a metric name, set or adjust a `target`/`weight`/`direction`, map a
metric twice, or return a score. Those are structurally impossible, not merely discouraged:

- `output_type=AgentMappingProposal` means the model can only return mappings — the schema has
  no score field.
- `@mapping_agent.output_validator` rejects unknown metric names, columns absent from the file,
  and duplicate assignments, raising `ModelRetry` so the model must correct itself.
- `_merge_proposal` re-checks every suggestion against the resolved profile and discards
  cross-profile metrics with a warning. An explicit `profile` from the caller always wins over
  the agent's choice.
- Retry exhaustion raises `AIMappingError` (502) rather than escaping as a 500.

Its three tools live in the same module. `check_mapping` is the important one: it scores real
sample values with `normalize_metric` — the same function used for the final result — so the
agent can catch its own scale errors (a 0-1 ratio against a target of 120 scores near zero).
**Tools own all arithmetic; the agent only reads their output.**

Trust is reported, never assumed: every mapping comes back in `resolved_mappings` with
`source: "alias" | "ai"`, a confidence, and the model's stated reasoning. Mappings below
`ai_mapping_low_confidence` are applied but listed in `warnings`.

### 7b. The report writer

The AI may: summarize performance, explain why a family scored high or low **using the
supplied components**, flag patterns and possible issues, and suggest next steps.

The AI may not: compute or adjust scores, fill in missing metrics, invent metrics that are not
in the payload, or state conclusions unsupported by the provided data.

Enforcement in practice:

- The prompt receives a compact JSON of the *already computed* `EmployeeKpiResult`, including
  missing-metric notes — never the raw file.
- The system prompt states the constraints and instructs the model to say "not enough data"
  instead of guessing.
- The response is stored as `narrative` text alongside the numbers. **Report text is never
  parsed back into numeric fields.**
- `temperature` stays low (see `ai_report.py`).
- No API key → deterministic fallback summary, and `ReportResponse.generated_by` says which
  path produced it. Callers can always tell.

---

## 8. API conventions

- Prefix: `/api/v1`. Routers are thin: parse → call one service → return a Pydantic model.
- Always declare `response_model`. Response models live in `schemas/`, never inline dicts.
- Never `raise HTTPException` from a service. Raise an `AppError` subclass from
  `core/errors.py`; the registered handlers convert it to a consistent `ErrorResponse`
  (`{"error": {"code", "message", "details"}}`).
- Validation failures inside a *file* are **not** HTTP errors: a file with 3 bad rows out of
  100 returns `200` with those rows listed in `issues`. Only a file that is unusable
  (wrong type, unparseable, no recognizable identifier column) is a `4xx`.
- Uploads: enforce extension allowlist and `settings.max_upload_bytes` before parsing.

Current endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | liveness + whether AI is configured |
| `GET` | `/api/v1/profiles` | role profiles + expected columns (dashboard hint) |
| `POST` | `/api/v1/uploads` | multipart file (+ optional `profile`, `mapping_mode`) → KPI results |
| `GET` | `/api/v1/batches` | list ingested batches |
| `GET` | `/api/v1/batches/{batch_id}` | full KPI result for a batch |
| `POST` | `/api/v1/reports` | AI narrative for one employee in a batch |

---

## 9. Persistence (MVP)

`core/store.py` is an in-memory dict keyed by `batch_id`, wrapped behind a tiny interface so a
real datastore can replace it later. State is lost on restart — that is accepted for the MVP.
Do not add a database without asking.

---

## 10. Style

- **No module-level docstrings or header comment blocks.** Files start directly with their
  first import or statement — no summary of what the file contains at the top. Architectural
  context belongs in this file, not repeated across source headers.
- Full type hints; modern syntax (`str | None`, `list[X]`, `dict[str, float]`).
- `snake_case` functions, `PascalCase` models, canonical metric names in `snake_case`.
- Docstrings on public *functions* are fine and wanted: what it does, what it raises. Explain
  *why* in inline comments, not *what*.
- Small pure functions in `utils/`; keep pandas usage inside `file_processor.py` so the rest of
  the codebase deals in plain Pydantic models.
- No `print` in library code.

---

## 11. Working agreements for coding tasks

1. Read the relevant service before editing; follow existing patterns over inventing new ones.
2. New logic goes into a **service**, not a route handler.
3. Reach for the simplest thing that satisfies the requirement; no speculative abstraction.
4. Touch only what the task needs — no drive-by refactors, no reformatting unrelated files.
5. New format/role support = a `profiles.py` entry. Nothing else.
6. Exercise the change against the running dev server before reporting done, and say plainly if
   anything fails.

---

## 12. Deliberately out of scope for now

Auth/multi-tenancy, database + migrations, background jobs, webhook ingestion (the service
layer is already shaped for it — a webhook route will call the same `ingest_file`), historical
trends, PDF export, streaming AI responses, rate limiting.

**Known gap worth fixing early: mappings are not remembered.** Every upload re-runs the agent
from scratch, so the same customer file costs tokens every month and could in principle be
mapped differently between runs. The fix is to persist an accepted mapping per customer/file
shape and reuse it, dropping to the agent only for genuinely new columns. That needs somewhere
to store it, which is why it is not in the MVP.
