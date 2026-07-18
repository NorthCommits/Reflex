# Reflex: Build Plan

This document is the single source of truth for building Reflex. Read it fully before writing any code. Build in the milestone order given at the end. Do not skip ahead, and do not add anything that is not described here without asking first.

## 1. What Reflex is

Reflex is a talk-to-your-data service. A user asks a question in plain English over HTTP. Reflex turns the question into a single read-only SQL query, runs it against a Postgres database, checks the result, repairs and retries the query if something is wrong, and returns the answer along with the exact SQL it ran and the full trace of its attempts.

The self-correcting loop is the product. This is a loop-engineering project, not a prompt wrapper. The model only proposes SQL. A deterministic harness validates it, runs it, judges the result, and decides whether to stop or loop again.

## 2. The one honest constraint

Reflex can only answer what the database can answer. This is a feature, not a limitation.

- If a question maps to a query over the existing tables, run it and answer with the number and the SQL.
- If the question cannot be expressed over the schema (for example a "why" question, or data that does not exist), say so plainly and name the tables that do exist. Never invent a number.
- If the question is ambiguous (for example "the good customers"), the model should signal that it needs clarification rather than guessing.

## 3. Loop-engineering principles (non-negotiable)

Every one of these must be visibly true in the final system. If a milestone would break one of these, stop and ask.

1. Model proposes, harness disposes. The model returns a string of SQL and a short rationale. It never touches the database, the filesystem, or any tool directly.
2. Deterministic oracle. The stop signal comes from the database, not from the model grading itself. A query either executes and returns rows, or it errors.
3. Explicit stop condition. The loop ends on a valid, plausible result, on a model signal that the question is unanswerable, or on budget exhaustion. Never on "the model produced text."
4. Hard budgets. A maximum attempt count, a per-statement timeout, and a row cap. All three are enforced by the harness and configurable.
5. Guardrails on every statement. Read-only at the database role level, plus statement parsing that rejects anything that is not a single SELECT.
6. Full trace. Every attempt records the proposed SQL, the validation outcome, the execution outcome, and the decision. The trace is returned in the API response and written to the logs.
7. Honest failure. When the budget is exhausted, Reflex says it could not answer reliably and shows what it tried. It does not fall back to a guess.

## 4. Tech stack

- Python 3.12
- FastAPI, served by uvicorn
- SQLAlchemy 2.x (declarative models)
- Alembic for migrations
- Postgres 16 (via Docker)
- pydantic-settings for configuration
- google-genai for Gemini (import `from google import genai`). Do not use the deprecated `google-generativeai` package.
- sqlglot for SQL parsing and validation
- Standard library logging, configured centrally via dictConfig
- Docker and docker compose

Gemini specifics: use `client.models.generate_content` with `model="gemini-flash-latest"` (currently resolves to gemini-3.5-flash) set in config. Use structured JSON output by passing `response_mime_type="application/json"` and a `response_schema` in the GenerateContentConfig, so the propose step returns clean JSON rather than prose we have to parse. Verify the current model alias against the Gemini API docs before finalising.

## 5. The harness boundary

The harness is the deterministic layer that owns everything the model is not allowed to touch:

- the two database connections (see below),
- SQL validation,
- execution with timeout and row cap,
- the stop and budget decisions,
- the trace.

Gemini receives context and returns JSON. That is the entire extent of the model's authority.

Two database connections, created from two env-provided URLs:

- A writer connection, used only by Alembic and the seed script.
- A read-only connection, used by the query executor. It authenticates as a Postgres role that has been granted SELECT only. Even if a bad statement slips past parsing, the database itself will refuse to write.

## 6. The agent loop

Given one user question, the harness runs this loop. Assign a correlation id to the question at the start and attach it to every log line and trace entry for that question.

1. Build context. Assemble the formatted schema, the user question, the bodies of the selected skills (see section 7), and the history of prior attempts in this loop (each prior SQL plus what went wrong).
2. Propose. Call Gemini. It returns JSON with one of two shapes: either `{ "answerable": true, "sql": "...", "reason": "..." }` or `{ "answerable": false, "explanation": "..." }`.
3. Short-circuit on unanswerable. If `answerable` is false, return the explanation plus the list of available tables. Do not loop.
4. Validate. Parse the SQL with sqlglot. Reject it if it is not exactly one statement, if it is not a SELECT, or if it contains any DDL or DML keyword. If it has no LIMIT, append one at the configured row cap. A rejection counts as a failed attempt and its reason is fed back into the next iteration.
5. Execute. Run the validated SQL on the read-only connection with the configured statement timeout.
6. Observe. Capture one of: a database error, an empty result, or rows.
7. Decide.
   - On rows, or on an empty result the model expected, format the answer and stop.
   - On a database error, append the error text to the attempt history and loop.
8. Budget. If the attempt count reaches the configured maximum, stop and return the honest failure message with the full trace of what was tried.

Keep the loop controller in one file (`harness.py`) and keep it readable. The steps above should map almost one to one onto the code.

## 7. Skills and the skill registry

A skill is a unit of SQL-writing guidance that is injected into the prompt only when relevant. Skills keep the base prompt small and make the system easy to extend.

### Skill file format

Each skill is a Markdown file in `reflex/skills/library/` with YAML frontmatter and a body:

```
---
name: date_filtering
description: When the question involves time ranges, relative dates, or grouping by day, week, month, or year.
---

Guidance text on how to handle dates in Postgres, written for the model.
Include one or two short example snippets showing the correct pattern.
```

- `name` is a unique slug.
- `description` states when the skill applies. This is the only part read during selection.
- The body is guidance plus one or two example SQL snippets. Keep it short and concrete.

### The registry

`reflex/skills/registry.py` loads every skill file at startup, parses the frontmatter, and exposes the list of skills with their names, descriptions, and bodies. It validates that every skill has the required fields and fails loudly at startup if one is malformed.

### Selection strategy for v1

Inject all skills into every prompt while the set is small. Do not build a skill selector yet. A selector is the correct thing to add only once the skill set grows large enough that context cost matters, and adding one now is premature. Structure the registry so that a selection step could be dropped in later without reshaping anything else.

### Initial skills to create

Create exactly these three skills to start, each following the format above:

1. `joins` - when the question spans more than one table. Explain the foreign-key relationships in this schema and show a correct multi-table join.
2. `date_filtering` - when the question involves time ranges or grouping by period. Show Postgres date_trunc and interval patterns.
3. `aggregation` - when the question asks for counts, sums, averages, or top-N. Show GROUP BY, aggregate functions, and ORDER BY with LIMIT.

## 8. Database schema

Five tables, a simple sales domain that any reviewer understands instantly. Define them as SQLAlchemy models.

- `customers`: id, name, country, signup_date
- `products`: id, name, category, price
- `orders`: id, customer_id (FK customers), order_date, status
- `order_items`: id, order_id (FK orders), product_id (FK products), quantity, unit_price
- `payments`: id, order_id (FK orders), amount, paid_date

This shape exercises joins across four tables, date bucketing over order_date and signup_date, and aggregation for revenue and counts. That is exactly what lights up the three skills.

### Alembic

- Configure `alembic/env.py` to read the writer database URL from the environment and to target the models' metadata.
- The initial migration creates all five tables.
- Migrations run automatically on container start (see section 11), not by hand.

### Seed data

- `seed.py` populates a fixed, deterministic dataset (use a fixed random seed so the numbers never drift between runs). A few hundred rows total is enough.
- Seeding must be idempotent: check whether the tables are already populated and do nothing if so.
- Seeding runs automatically on container start, after migrations.

### Read-only role

- Create a Postgres role for the executor with a login and no write privileges.
- Grant it SELECT on all five tables. Set default privileges so future tables are covered.
- The role is created at database initialisation. The SELECT grants are applied by the entrypoint after migrations have created the tables.
- The read-only connection URL points at this role. The executor uses only this connection.

## 9. FastAPI surface

Keep the API small and honest. Every response that involves the loop must expose the trace.

- `POST /ask` - body `{ "question": "..." }`. Returns `{ "status": "answered" | "unanswerable" | "failed", "answer": "...", "sql": "...", "attempts": [ ... ], "correlation_id": "..." }`. `attempts` is the trace: a list where each entry holds the proposed SQL, the validation result, the execution result or error, and the decision.
- `GET /schema` - returns the introspected schema. Useful for the demo.
- `GET /skills` - returns the loaded skills with their names and descriptions. Shows the registry working.
- `GET /health` - liveness check, confirms the app is up and the database is reachable.

## 10. Logging

Good logs are a first-class requirement, not an afterthought.

- Configure logging once, centrally, using `logging.config.dictConfig` in a single module. No scattered `logging.basicConfig` calls.
- Every log line carries: ISO-8601 timestamp, level, logger name, the correlation id of the current question, and the message. Use a contextvar to carry the correlation id so it is attached automatically without threading it through every function call.
- Log levels used deliberately: INFO for the lifecycle of each question and each loop iteration (proposed, validated, executed, decided), WARNING for guardrail rejections and budget exhaustion, ERROR for unexpected failures with a stack trace.
- Log the SQL and the outcome of each attempt so a single question's whole loop can be reconstructed from the logs alone.
- Never log the Gemini API key or any secret.
- Default log level comes from config. Support a plain human-readable console format; a JSON format toggle is a nice-to-have, not required for v1.

## 11. Docker and entrypoint

`docker compose up` must bring up a working, seeded, ready-to-query service with no manual steps.

- A `Dockerfile` for the app.
- A `docker-compose.yml` with two services: `db` (Postgres 16) and `app`. The app depends on the db being healthy (use a healthcheck on the db service).
- Create the read-only role at database initialisation using a SQL script mounted into the Postgres init directory.
- An `entrypoint.sh` for the app that runs in this order: wait for the database to be reachable, run `alembic upgrade head`, apply the SELECT grants to the read-only role, run the seed script, then start uvicorn.
- All secrets and URLs come from the environment. The compose file wires the two database URLs and passes GEMINI_API_KEY through from the host `.env`.

## 12. Configuration

A single `config.py` using pydantic-settings, reading from the environment and `.env`:

- `gemini_api_key`
- `model_name` (default `gemini-flash-latest`)
- `database_url` (writer, for Alembic and seed)
- `readonly_database_url` (executor)
- `max_attempts` (default 4)
- `row_limit` (default 200)
- `statement_timeout_ms` (default 5000)
- `log_level` (default INFO)

Nothing reads the environment directly except this module. Everything else imports the settings object.

## 13. Project structure

```
reflex/
  reflex/
    __init__.py
    config.py           settings via pydantic-settings
    logging_config.py   dictConfig setup and correlation-id contextvar
    db.py               engines and sessions for writer and read-only
    models.py           SQLAlchemy models for the five tables
    schema.py           introspects and formats the schema for the prompt
    llm.py              thin google-genai client, the propose call
    executor.py         validate and run SQL on the read-only connection
    harness.py          the loop controller, stop condition, budget, trace
    trace.py            the trace data structures
    skills/
      registry.py       loads and serves skills
      library/
        joins.md
        date_filtering.md
        aggregation.md
    api.py              FastAPI app and routes
  alembic/
    env.py
    versions/
  seed.py               deterministic idempotent seed
  entrypoint.sh
  Dockerfile
  docker-compose.yml
  init-readonly-role.sql
  pyproject.toml
  .env                  (already present, holds GEMINI_API_KEY)
  .gitignore            (already present)
  plan.md               (this file)
```

## 14. Coding conventions and constraints

- Keep the structure simple. Prefer plain functions and small modules over classes and layers of abstraction. Do not introduce a pattern until the code actually needs it.
- No premature abstraction. No skill selector, no plugin system, no base classes with one implementation.
- Type-hint public functions. Keep functions short and single-purpose.
- Comments explain why, not what, and are written in plain natural language. Do not over-comment.
- Do not use emojis anywhere. Do not use em-dashes anywhere, in code, comments, strings, or docs. Use commas or shorter sentences instead.
- Handle errors explicitly. Database errors in the loop are expected control flow, not crashes. Unexpected errors are logged with a stack trace.
- Pin dependency versions in `pyproject.toml`.

## 15. How to work through this (guidance for Claude Code)

- Read this whole document first. Then build in the milestone order below, one milestone at a time.
- After each milestone, stop, state what you built, and how it can be tested. Do not start the next milestone until the current one is verified.
- If a milestone is blocked or the plan is ambiguous or the plan seems wrong, stop and ask rather than guessing or inventing scope.
- Prefer the simplest thing that satisfies the milestone. Flag anything that feels like over-engineering.
- Test each milestone against the real sample database, not mocks, wherever a database is involved.

### Milestones

1. Project skeleton and config. `pyproject.toml`, `config.py`, `logging_config.py`. Verify: the app imports, settings load from `.env`, a test log line carries a correlation id.
2. Models and Alembic. `models.py`, Alembic wired up, initial migration. Verify: `alembic upgrade head` creates all five tables in a local Postgres.
3. Seed. `seed.py`, deterministic and idempotent. Verify: running it twice leaves the same row counts, and the data looks sane.
4. Schema introspection. `schema.py`. Verify: it prints a clean, prompt-ready description of the five tables and their relationships.
5. Executor and guardrails. `executor.py` and the read-only connection. Verify: a valid SELECT returns rows, a non-SELECT is rejected by parsing, and a write attempt is refused by the database role even if parsing were bypassed.
6. Gemini propose step. `llm.py`. Verify: given the schema and one hardcoded question, it returns valid JSON in the expected shape.
7. Skills and registry. The three skill files and `registry.py`. Verify: skills load at startup, malformed skills fail loudly, and `GET /skills` will later be able to list them.
8. The harness. `harness.py`, `trace.py`. Tie the loop together with the stop condition, budget, and trace. Verify: a question that needs one repair visibly loops and then succeeds, and an impossible question exhausts the budget and fails honestly.
9. FastAPI surface. `api.py` with the four routes. Verify: `POST /ask` returns the answer, the SQL, and the trace for a real question.
10. Docker and entrypoint. Dockerfile, compose, entrypoint, read-only role init. Verify: a clean `docker compose up` yields a seeded service that answers a question end to end with no manual steps.
11. Demo polish. Confirm the trace reads well, the honest-failure and unanswerable paths look good, and the logs cleanly reconstruct a single question's loop.