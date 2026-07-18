# Reflex

Reflex is a talk-to-your-data service. Ask a question in plain English over HTTP, and
Reflex turns it into a single read-only SQL query, runs it against Postgres, checks the
result, repairs and retries the query if something is wrong, and returns the answer along
with the exact SQL it ran and the full trace of every attempt.

The self-correcting loop is the product. The model only proposes SQL; a deterministic
harness validates it, runs it, judges the result, and decides whether to stop or loop
again.

## The one honest constraint

Reflex can only answer what the database can answer.

- If a question maps to a query over the existing tables, it runs the query and answers
  with the number and the SQL.
- If the question can't be expressed over the schema (a "why" question, or data that
  doesn't exist), it says so plainly and names the tables that do exist. It never invents
  a number.
- If the question is ambiguous (for example "the good customers"), it asks for
  clarification instead of guessing a definition.

## Quickstart

```bash
cp .env.example .env   # if you don't already have one, then fill in GEMINI_API_KEY
docker compose up --build
```

That's it. On first run this builds the image, starts Postgres, waits for it to be
healthy, runs the Alembic migration, grants the read-only role SELECT on the new tables,
seeds a deterministic sample dataset, and starts the API. No manual steps.

The app listens on `http://localhost:8010` (mapped from container port 8000).

```bash
curl -s http://localhost:8010/health

curl -s -X POST http://localhost:8010/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the top 3 product categories by total revenue?"}' | python3 -m json.tool
```

## The sample data

A small sales domain: `customers`, `products`, `orders`, `order_items`, `payments`.
Deterministic and idempotent, ~1,500 rows total across the five tables (120 customers,
105 products, 300 orders, 795 order items, 221 payments). Re-running the seed script is a
no-op once the tables are populated.

## API

- `POST /ask` - body `{ "question": "..." }`. Returns:
  ```json
  {
    "status": "answered | unanswerable | failed",
    "answer": "human-readable answer or explanation",
    "sql": "the exact SQL that produced the answer, or null",
    "attempts": [ { "attempt_number": 1, "proposed_sql": "...", "validation_ok": true, "execution_ok": true, "decision": "stopped: success", "...": "..." } ],
    "correlation_id": "...",
    "available_tables": null
  }
  ```
  `attempts` is the full trace: every proposed query, whether it validated, whether it
  executed, and what the harness decided. `available_tables` is populated for
  `unanswerable` and `failed` responses.
- `GET /schema` - the introspected schema (tables, columns, types, foreign keys).
- `GET /skills` - the loaded skill names and descriptions.
- `GET /health` - liveness check; confirms the app is up and the database is reachable.

## How the loop works

Each question gets a correlation id that's attached to every log line and trace entry for
that request, so a single question's whole loop can be reconstructed from the logs alone.

1. **Build context**: schema, question, skill guidance, and the history of any prior
   failed attempts in this loop (SQL plus what went wrong).
2. **Propose**: call Gemini. It returns JSON: either
   `{"answerable": true, "sql": "...", "reason": "..."}` or
   `{"answerable": false, "explanation": "..."}`.
3. **Short-circuit on unanswerable**: if the model says the question can't be answered
   (or is too ambiguous), stop and return its explanation. No loop.
4. **Validate**: parse the SQL with sqlglot. Reject anything that isn't exactly one
   `SELECT` statement, including data-modifying CTEs that smuggle a write inside a
   nominally read-only statement. Append a `LIMIT` if none was given.
5. **Execute**: run it on a read-only database connection with a statement timeout.
6. **Decide**: a clean execution (any row count, including zero) stops the loop with a
   success. A database error appends to the attempt history and loops.
7. **Budget**: after `MAX_ATTEMPTS` failed attempts, stop and return an honest failure
   with the full trace of what was tried. Reflex never falls back to a guess.

## Guardrails

Two database connections: a writer used only by Alembic and the seed script, and a
read-only connection used only by the query executor, authenticated as a Postgres role
granted `SELECT` and nothing else. Even if a bad statement slipped past SQL validation,
the database itself refuses to write.

## Configuration

Everything is read from the environment (and `.env` for local development) by
`reflex/config.py`. No other module reads the environment directly.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | required | Gemini API key |
| `MODEL_NAME` | `gemini-flash-latest` | Gemini model used for the propose step |
| `DATABASE_URL` | required | Writer connection (Alembic, seed) |
| `READONLY_DATABASE_URL` | required | Read-only connection (query executor) |
| `MAX_ATTEMPTS` | `4` | Max propose/validate/execute attempts per question |
| `ROW_LIMIT` | `200` | Row cap appended to queries with no `LIMIT` |
| `STATEMENT_TIMEOUT_MS` | `5000` | Per-statement timeout on the read-only connection |
| `LOG_LEVEL` | `INFO` | Log level |

Note: the Gemini free tier caps `gemini-flash-latest` at a low daily request quota
(20/day at time of writing). A `429` from Gemini during the loop is treated as a failed
attempt like any other and gets retried within the budget, but it's worth checking your
quota before a live demo with many questions.

## Local development (without Docker)

```bash
uv sync
cp .env.example .env   # fill in GEMINI_API_KEY and point the DB URLs at a local Postgres

alembic upgrade head
python seed.py
uvicorn reflex.api:app --reload
```

## Project layout

```
reflex/
  config.py           settings via pydantic-settings, the only module that reads the environment
  logging_config.py   dictConfig setup and the correlation-id contextvar
  db.py                writer and read-only engines/sessions
  models.py            SQLAlchemy models for the five tables
  schema.py             introspects and formats the schema for the prompt
  llm.py                the Gemini propose call
  executor.py           SQL validation and execution on the read-only connection
  harness.py             the loop controller: stop condition, budget, trace
  trace.py                the trace data structures
  skills/
    registry.py            loads and validates skills at startup
    library/                joins.md, date_filtering.md, aggregation.md
  api.py                  FastAPI app and routes
alembic/                  migrations
seed.py                    deterministic, idempotent seed script
entrypoint.sh               wait for db, migrate, grant, seed, serve
Dockerfile
docker-compose.yml
init-readonly-role.sql      creates the read-only role at database init time
```

## Tech stack

Python 3.12, FastAPI/uvicorn, SQLAlchemy 2.x, Alembic, Postgres 16, pydantic-settings,
`google-genai`, sqlglot.
