from dataclasses import dataclass


@dataclass
class Attempt:
    attempt_number: int
    proposed_sql: str | None
    propose_reason: str | None
    validation_ok: bool | None
    validation_error: str | None
    validated_sql: str | None
    execution_ok: bool | None
    execution_error: str | None
    row_count: int | None
    decision: str


@dataclass
class LoopResult:
    status: str  # "answered", "unanswerable", or "failed"
    correlation_id: str
    answer: str | None
    sql: str | None
    rows: list[dict] | None
    explanation: str | None
    available_tables: list[str] | None
    attempts: list[Attempt]
