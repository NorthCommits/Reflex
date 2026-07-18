from dataclasses import dataclass

from sqlalchemy import inspect

from reflex.db import writer_engine

# Schema introspection reads only table/column metadata, never row data, so
# it runs against the writer engine, which is guaranteed to exist regardless
# of when the read-only role's grants are applied.

# Alembic's own bookkeeping table is not part of the domain schema and must
# never be shown to the model or the demo.
EXCLUDED_TABLES = {"alembic_version"}


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    primary_key: bool


@dataclass
class ForeignKeyInfo:
    column: str
    references_table: str
    references_column: str


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo]


def introspect_schema() -> list[TableInfo]:
    inspector = inspect(writer_engine)
    tables = []

    for table_name in sorted(inspector.get_table_names()):
        if table_name in EXCLUDED_TABLES:
            continue

        pk_columns = set(inspector.get_pk_constraint(table_name)["constrained_columns"])

        columns = [
            ColumnInfo(
                name=col["name"],
                type=str(col["type"]),
                nullable=col["nullable"],
                primary_key=col["name"] in pk_columns,
            )
            for col in inspector.get_columns(table_name)
        ]

        foreign_keys = [
            ForeignKeyInfo(
                column=fk["constrained_columns"][0],
                references_table=fk["referred_table"],
                references_column=fk["referred_columns"][0],
            )
            for fk in inspector.get_foreign_keys(table_name)
        ]

        tables.append(TableInfo(name=table_name, columns=columns, foreign_keys=foreign_keys))

    return tables


def format_schema_for_prompt(tables: list[TableInfo] | None = None) -> str:
    """Render the schema as a compact, readable block for the LLM prompt."""
    if tables is None:
        tables = introspect_schema()

    lines = []
    for table in tables:
        lines.append(f"Table {table.name}:")
        for column in table.columns:
            markers = []
            if column.primary_key:
                markers.append("primary key")
            fk = next((fk for fk in table.foreign_keys if fk.column == column.name), None)
            if fk:
                markers.append(f"foreign key -> {fk.references_table}.{fk.references_column}")
            marker_text = f" ({', '.join(markers)})" if markers else ""
            lines.append(f"  {column.name}: {column.type}{marker_text}")
        lines.append("")

    return "\n".join(lines).strip()
