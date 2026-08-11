# AGENTS.md — Employee Performance Tracking Agent (Backend)

This file is the primary development guide for the backend. Read it before writing code.
If something here conflicts with a request, mention the conflict and follow the request.

---

## 1. What this service does

A FastAPI backend that:

1. Ingests performance data from **CSV/Excel uploads** and, later, a **webhook**.
2. Hands it to an **AI agent that decides what is worth calculating**.
3. Gives that agent **tools** that do the actual arithmetic.
4. Exposes the results for a **Vue dashboard**.

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

uv run fastapi dev app/main.py       # dev server, http://127.0.0.1:8000/docs
```

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
├── pyproject.toml            # deps + build config
├── .env.example
└── app/
    ├── main.py               # app, middleware, exception handlers, routers
    ├── api/                  # FastAPI routes — thin: parse, call one service, return
    │   ├── agent.py          # POST /ask
    │   └── health.py         # GET /health
    ├── schemas/              # Pydantic request/response + internal models ONLY
    │   └── agent.py          # AskRequest, AskResponse
    ├── services/             # all business logic lives here
    │   └── agent.py          # PydanticAI agent + its tools
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

**TODO — decide against a real data file, don't invent one.** Open: what summary the agent
sees of an uploaded file, the envelope wrapping its free-form results, and whether analysis
is per file or per entity.

---

## 6. Calculations

**TODO — how granular the agent's tools should be is the central open decision.** Generic
frame operations, or named calculators? Decide it against a real file.

Whatever they turn out to be: tools own all arithmetic, and every number returned must be
traceable to the tool call that produced it.

---

## 7. AI boundaries

Only the agent module may call a model. Nothing else, ever.

The agent **may**: inspect the data, decide what is worth calculating, call tools.
The agent **may not**: do arithmetic itself, or return a number it did not get from a tool.

Enforce this structurally — typed tool arguments, a typed output shape — rather than by
asking nicely in the prompt. Report what the agent chose and why alongside the results;
free-form output is not an excuse for an unexplained response.

No API key → the service still starts, and endpoints needing the agent say so plainly.

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
| `POST` | `/api/v1/ask` | send a prompt to the agent; returns its answer + token usage |

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

Auth/multi-tenancy, database + migrations, background jobs, historical trends, PDF export,
streaming AI responses, rate limiting, tests.
