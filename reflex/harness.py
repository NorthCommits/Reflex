import logging
import uuid

from reflex.config import settings
from reflex.executor import execute_sql, validate_sql
from reflex.llm import propose
from reflex.logging_config import correlation_id_var
from reflex.schema import format_schema_for_prompt, introspect_schema
from reflex.skills.registry import format_skills_for_prompt, select_skills
from reflex.trace import Attempt, LoopResult

logger = logging.getLogger("reflex.harness")

# The full row set is capped by row_limit already; this further caps what
# gets rendered into the human-readable answer text so a large result set
# does not dump hundreds of lines into the response.
_ANSWER_DISPLAY_LIMIT = 20


def _build_prompt(schema_text: str, skills_text: str, question: str, attempts: list[Attempt]) -> str:
    parts = [f"Schema:\n{schema_text}", f"Guidance:\n{skills_text}", f"Question: {question}"]

    failed = [a for a in attempts if a.proposed_sql is not None]
    if failed:
        history_lines = []
        for a in failed:
            problem = a.validation_error or a.execution_error or "unknown issue"
            history_lines.append(f"Attempt {a.attempt_number} SQL: {a.proposed_sql}\nProblem: {problem}")
        parts.append(
            "Prior attempts in this conversation failed. Fix the issue, do not repeat the "
            "same query:\n\n" + "\n\n".join(history_lines)
        )

    return "\n\n".join(parts)


_NO_DATA_MESSAGE = "The query ran successfully but found no matching data for that question."


def _format_answer(rows: list[dict]) -> str:
    no_rows = not rows
    all_null_row = len(rows) == 1 and all(v is None for v in rows[0].values())
    if no_rows or all_null_row:
        return _NO_DATA_MESSAGE

    if len(rows) == 1 and len(rows[0]) == 1:
        (value,) = rows[0].values()
        return str(value)

    display_rows = rows[:_ANSWER_DISPLAY_LIMIT]
    lines = [f"{len(rows)} row(s) returned."]
    for row in display_rows:
        lines.append(", ".join(f"{k}={v}" for k, v in row.items()))
    if len(rows) > _ANSWER_DISPLAY_LIMIT:
        lines.append(f"... and {len(rows) - _ANSWER_DISPLAY_LIMIT} more row(s).")
    return "\n".join(lines)


def ask(question: str) -> LoopResult:
    correlation_id = uuid.uuid4().hex[:12]
    token = correlation_id_var.set(correlation_id)

    try:
        logger.info("question received: %r", question)

        schema_text = format_schema_for_prompt()
        selected_skills = select_skills(question)
        logger.info("selected skills: %s", [s.name for s in selected_skills])
        skills_text = format_skills_for_prompt(selected_skills)
        table_names = [t.name for t in introspect_schema()]

        attempts: list[Attempt] = []

        for attempt_number in range(1, settings.max_attempts + 1):
            prompt = _build_prompt(schema_text, skills_text, question, attempts)

            try:
                logger.info("attempt %d: proposing", attempt_number)
                proposal = propose(prompt)
            except Exception:
                logger.error("attempt %d: propose call failed unexpectedly", attempt_number, exc_info=True)
                attempts.append(
                    Attempt(
                        attempt_number=attempt_number,
                        proposed_sql=None,
                        propose_reason=None,
                        validation_ok=None,
                        validation_error="The proposal call failed unexpectedly.",
                        validated_sql=None,
                        execution_ok=None,
                        execution_error=None,
                        row_count=None,
                        decision="looped: propose failed",
                    )
                )
                continue

            if not proposal.answerable:
                logger.info("attempt %d: model signalled unanswerable", attempt_number)
                attempts.append(
                    Attempt(
                        attempt_number=attempt_number,
                        proposed_sql=None,
                        propose_reason=None,
                        validation_ok=None,
                        validation_error=None,
                        validated_sql=None,
                        execution_ok=None,
                        execution_error=None,
                        row_count=None,
                        decision="stopped: unanswerable",
                    )
                )
                return LoopResult(
                    status="unanswerable",
                    correlation_id=correlation_id,
                    answer=None,
                    sql=None,
                    rows=None,
                    explanation=proposal.explanation,
                    available_tables=table_names,
                    attempts=attempts,
                )

            logger.info("attempt %d: validating proposed SQL", attempt_number)
            validation = validate_sql(proposal.sql)

            if not validation.ok:
                logger.warning("attempt %d: validation rejected: %s", attempt_number, validation.error)
                attempts.append(
                    Attempt(
                        attempt_number=attempt_number,
                        proposed_sql=proposal.sql,
                        propose_reason=proposal.reason,
                        validation_ok=False,
                        validation_error=validation.error,
                        validated_sql=None,
                        execution_ok=None,
                        execution_error=None,
                        row_count=None,
                        decision="looped: validation failed",
                    )
                )
                continue

            logger.info("attempt %d: executing validated SQL", attempt_number)
            execution = execute_sql(validation.sql)

            if not execution.ok:
                logger.warning("attempt %d: execution failed: %s", attempt_number, execution.error)
                attempts.append(
                    Attempt(
                        attempt_number=attempt_number,
                        proposed_sql=proposal.sql,
                        propose_reason=proposal.reason,
                        validation_ok=True,
                        validation_error=None,
                        validated_sql=validation.sql,
                        execution_ok=False,
                        execution_error=execution.error,
                        row_count=None,
                        decision="looped: execution failed",
                    )
                )
                continue

            logger.info("attempt %d: succeeded with %d row(s)", attempt_number, len(execution.rows))
            attempts.append(
                Attempt(
                    attempt_number=attempt_number,
                    proposed_sql=proposal.sql,
                    propose_reason=proposal.reason,
                    validation_ok=True,
                    validation_error=None,
                    validated_sql=validation.sql,
                    execution_ok=True,
                    execution_error=None,
                    row_count=len(execution.rows),
                    decision="stopped: success",
                )
            )
            return LoopResult(
                status="answered",
                correlation_id=correlation_id,
                answer=_format_answer(execution.rows),
                sql=validation.sql,
                rows=execution.rows,
                explanation=None,
                available_tables=None,
                attempts=attempts,
            )

        logger.warning("budget of %d attempts exhausted", settings.max_attempts)
        return LoopResult(
            status="failed",
            correlation_id=correlation_id,
            answer=None,
            sql=None,
            rows=None,
            explanation=(
                "Reflex could not answer this reliably within the attempt budget. "
                "See the attempts below for what was tried."
            ),
            available_tables=table_names,
            attempts=attempts,
        )
    finally:
        correlation_id_var.reset(token)
