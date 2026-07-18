import json
import logging
from dataclasses import dataclass

from google import genai
from google.genai import types

from reflex.config import settings

logger = logging.getLogger("reflex.llm")

_client = genai.Client(api_key=settings.gemini_api_key)

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean"},
        "sql": {"type": "string"},
        "reason": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["answerable"],
}

_SYSTEM_INSTRUCTION = """You are the SQL-proposing component of Reflex, a talk-to-your-data \
service. You are given a Postgres schema, relevant guidance, a user question, and the \
history of any prior failed attempts. You never touch the database yourself, you only \
propose.

Respond with JSON matching one of these two shapes:
- If the question can be answered with a single read-only SQL query over the given \
schema: {"answerable": true, "sql": "<the SELECT statement>", "reason": "<why this query \
answers the question>"}
- If the question cannot be answered over this schema (it asks about data that does not \
exist, asks "why" something happened, or turns on a subjective or undefined term such as \
"good" customers, "important" products, or "best" performance with no stated metric): \
{"answerable": false, "explanation": "<if data is missing, name what tables do exist; if \
the question is ambiguous, say what is unclear and name the concrete metrics that would \
resolve it, such as total spend, order count, or recency, rather than picking one for the \
user>"}

Never silently pick a definition for an ambiguous or subjective term and answer as if the \
user had specified it. Ask for clarification instead.

The SQL must be a single SELECT statement. Never use INSERT, UPDATE, DELETE, DROP, \
ALTER, or any statement that writes or changes schema. If a prior attempt failed, read \
the error and fix the query rather than repeating it."""


@dataclass
class ProposeResult:
    answerable: bool
    sql: str | None
    reason: str | None
    explanation: str | None


def propose(prompt: str) -> ProposeResult:
    """Call Gemini with the assembled context and return its structured proposal."""
    response = _client.models.generate_content(
        model=settings.model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
            # The model spends some of its output budget on internal
            # reasoning before the visible JSON. Too low a cap truncates
            # the JSON mid-string, so this must stay generous.
            max_output_tokens=4096,
        ),
    )

    data = json.loads(response.text)
    answerable = data.get("answerable")

    if answerable is None:
        raise ValueError(f"Gemini response missing 'answerable' field: {response.text}")

    logger.info("propose returned answerable=%s", answerable)

    return ProposeResult(
        answerable=answerable,
        sql=data.get("sql"),
        reason=data.get("reason"),
        explanation=data.get("explanation"),
    )
