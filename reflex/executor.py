import logging
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from reflex.config import settings
from reflex.db import readonly_engine

logger = logging.getLogger("reflex.executor")

# Node types that indicate a write, a schema change, or a session/admin
# command. Checked across every node in the parsed tree, not just the top
# level, because Postgres allows data-modifying statements inside a CTE
# (e.g. "with x as (delete from orders returning *) select * from x") whose
# outer statement type is still Select.
_FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Merge,
    exp.Grant,
    exp.Set,
    exp.Copy,
    exp.Attach,
    exp.Detach,
    exp.Pragma,
)


@dataclass
class ValidationResult:
    ok: bool
    sql: str | None
    error: str | None


@dataclass
class ExecutionResult:
    ok: bool
    rows: list[dict] | None
    error: str | None


def validate_sql(raw_sql: str) -> ValidationResult:
    """Parse and guardrail a proposed SQL string.

    Rejects anything that is not exactly one SELECT statement, or that
    contains a write, DDL, or admin node anywhere in its tree. Appends a
    LIMIT at the configured row cap if the query has none.
    """
    try:
        statements = sqlglot.parse(raw_sql, read="postgres")
    except Exception as exc:
        logger.warning("sql validation rejected: parse error: %s", exc)
        return ValidationResult(ok=False, sql=None, error=f"SQL parse error: {exc}")

    statements = [s for s in statements if s is not None]

    if len(statements) != 1:
        logger.warning("sql validation rejected: expected 1 statement, got %d", len(statements))
        return ValidationResult(
            ok=False,
            sql=None,
            error=f"Expected exactly one SQL statement, got {len(statements)}.",
        )

    statement = statements[0]

    if not isinstance(statement, exp.Select):
        logger.warning("sql validation rejected: not a SELECT (%s)", type(statement).__name__)
        return ValidationResult(
            ok=False,
            sql=None,
            error=f"Only SELECT statements are allowed, got {type(statement).__name__}.",
        )

    for node in statement.walk():
        if isinstance(node, _FORBIDDEN_NODE_TYPES):
            logger.warning("sql validation rejected: forbidden node %s", type(node).__name__)
            return ValidationResult(
                ok=False,
                sql=None,
                error=f"Query contains a disallowed operation: {type(node).__name__}.",
            )

    if statement.args.get("limit") is None:
        statement = statement.limit(settings.row_limit)

    validated_sql = statement.sql(dialect="postgres")
    return ValidationResult(ok=True, sql=validated_sql, error=None)


def execute_sql(validated_sql: str) -> ExecutionResult:
    """Run already-validated SQL on the read-only connection with a statement timeout."""
    try:
        with readonly_engine.connect() as conn:
            conn.execute(text(f"SET statement_timeout = {settings.statement_timeout_ms}"))
            result = conn.execute(text(validated_sql))
            rows = [dict(row._mapping) for row in result.fetchall()]
        return ExecutionResult(ok=True, rows=rows, error=None)
    except (DBAPIError, SQLAlchemyError) as exc:
        logger.warning("sql execution failed: %s", exc)
        return ExecutionResult(ok=False, rows=None, error=str(exc.orig) if hasattr(exc, "orig") else str(exc))
