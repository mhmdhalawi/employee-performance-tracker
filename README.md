# Performance Tracking Agent — Backend

FastAPI service that ingests CSV or Excel performance data, gives a bounded workbook synopsis
to an AI agent for semantic mapping, validates the mapped records, and calculates employee
Productivity, Compliance, and Quality scores deterministically in Python.

`POST /api/v1/analyze` returns employee KPI results, validation findings, mapping limitations,
token/request diagnostics, and whether a validated in-memory schema mapping was reused.

## Quick start

```bash
uv sync
cp .env.example .env          # set OPENAI_API_KEY when the agent lands
uv run fastapi dev app/main.py
```

Open http://127.0.0.1:8000/docs.

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

The service is in an early stage. This table lists endpoints that are available now.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | liveness + whether AI is configured |

## Development guide

**Read [AGENTS.md](AGENTS.md) before writing code** — architecture, the AI boundary, and
conventions live there.
