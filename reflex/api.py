from dataclasses import asdict

from reflex.config import settings
from reflex.logging_config import configure_logging

# Logging must be configured before any other reflex module logs at import
# time (the skills registry logs its load result on import).
configure_logging(settings.log_level)

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from reflex.db import readonly_engine
from reflex.harness import ask as run_ask
from reflex.schema import introspect_schema
from reflex.skills.registry import get_skills

logger = logging.getLogger("reflex.api")

app = FastAPI(title="Reflex")


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(request: AskRequest):
    result = run_ask(request.question)
    return {
        "status": result.status,
        "answer": result.answer if result.answer is not None else result.explanation,
        "sql": result.sql,
        "attempts": [asdict(a) for a in result.attempts],
        "correlation_id": result.correlation_id,
        "available_tables": result.available_tables,
    }


@app.get("/schema")
def get_schema():
    tables = introspect_schema()
    return [asdict(t) for t in tables]


@app.get("/skills")
def get_skills_endpoint():
    return [{"name": s.name, "description": s.description} for s in get_skills()]


@app.get("/health")
def health():
    try:
        with readonly_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.error("health check failed: database unreachable", exc_info=True)
        raise HTTPException(status_code=503, detail="database unreachable")
    return {"status": "ok"}
