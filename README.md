# Performance Tracking Agent — Backend

FastAPI service that ingests performance data (CSV/Excel now, webhook later) and hands it to
an AI agent that decides what is worth calculating. The agent interprets the data and calls
Python tools to do the arithmetic — it never computes numbers itself.

Early stage: right now this is a health endpoint and nothing else.

## Quick start

```bash
uv sync
cp .env.example .env          # set OPENAI_API_KEY when the agent lands
uv run fastapi dev app/main.py
```

Open http://127.0.0.1:8000/docs.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | liveness + whether AI is configured |

## Development guide

**Read [AGENTS.md](AGENTS.md) before writing code** — architecture, the AI boundary, and
conventions live there.
