# Employee Performance Tracking Agent — Backend

FastAPI service that ingests employee performance files (CSV/Excel), calculates
Productivity / Quality / Compliance KPI scores deterministically, and generates AI
narratives that *explain* those calculated scores.

Unrecognized spreadsheet columns are resolved by a PydanticAI agent that maps them onto the
canonical metrics the backend already knows how to score. The agent decides what the data
*means*; all arithmetic stays in `kpi_engine`, and every mapping it chose is reported back with
its confidence.

## Quick start

```bash
uv sync
cp .env.example .env          # optional: set OPENAI_API_KEY for real AI reports
uv run fastapi dev app/main.py
```

Open http://127.0.0.1:8000/docs.

Without an API key the service runs fine — report generation falls back to a
deterministic template summary.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | liveness + whether AI is configured |
| `GET` | `/api/v1/profiles` | role profiles and their accepted columns |
| `POST` | `/api/v1/uploads` | multipart file (+ optional `profile`, `mapping_mode`) → KPI results |
| `GET` | `/api/v1/batches` | list ingested batches |
| `GET` | `/api/v1/batches/{batch_id}` | full KPI results for a batch |
| `POST` | `/api/v1/reports` | AI narrative for one employee in a batch |

## Development guide

**Read [AGENTS.md](AGENTS.md) before writing code** — architecture, the KPI contract,
AI boundaries, and conventions live there.
