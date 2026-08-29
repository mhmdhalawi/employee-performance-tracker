# Performance Tracking Agent

Employee performance analysis application with a FastAPI backend and a Vue 3 browser client.
It ingests CSV or Excel performance data, gives a bounded workbook synopsis to an AI agent
for KPI-family classification and calculator planning, validates the bound records, and calculates employee Productivity,
Compliance, and Quality scores deterministically in Python.

`POST /api/v1/analyze` returns employee KPI results, validation findings, applied filters,
weekly KPI trends, traceable alerts, classification limitations, token/request diagnostics, and
whether a validated in-memory calculation plan was reused.

The frontend lives in `web/` and uses Vue 3, TypeScript, Vite, Tailwind CSS v4, and
shadcn-vue. The backend remains authoritative for validation, KPI calculations, evidence
confidence, and trend calculations.

After an analysis, the browser client provides employee, team, and reporting-period filters;
summary KPIs; sortable, paginated employee results with alert counts; weekly KPI trends; and a
responsive employee detail sheet containing traceable alerts and on-demand AI guidance. A
data-interpretation card and detail sheet show each table's KPI classification, confidence,
selected calculator, and validated source-column bindings.
Analysis state remains in browser memory and is not persisted across a page refresh.

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

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to enable `/ask` and `/analyze`.
The service still starts without a key, and `/api/v1/health` reports whether AI is
configured.

Run the backend from the repository root in one terminal:

```bash
uv run fastapi dev app/main.py
```

The API documentation is available at http://127.0.0.1:8000/docs.

Run the deterministic service regression suite from the repository root:

```bash
uv run python -m unittest discover -s tests -v
```

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

## Development guide

**Read [AGENTS.md](AGENTS.md) before writing code** — architecture, the AI boundary, and
conventions live there.
