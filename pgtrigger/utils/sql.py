"""
Turning SQLAlchemy expressions and Python heredocs into PostgreSQL SQL.
"""

from textwrap import dedent
from typing import TYPE_CHECKING

from pgtrigger.consts import DOLLAR_TAG_PATTERN, PG_DIALECT

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

########################################################################################


def compile_expression(expression: ColumnElement) -> str:
    """
    Render a SQLAlchemy expression as standalone PostgreSQL SQL.

    Bind parameters are inlined, since a trigger definition cannot carry any.

    Returns:
        str: The rendered expression.

    """

    compiled = expression.compile(
        compile_kwargs={"literal_binds": True, "include_table": True},
        dialect=PG_DIALECT,
    )

    return str(compiled).strip()


def dedent_sql(sql: str) -> str:
    """
    Normalise a SQL fragment written as an indented Python string.

    Strips the common leading indentation, drops blank lines, and removes
    trailing whitespace from each line, so a fragment that reads well in source
    also reads well in `pg_get_functiondef` output.

    Blank lines go because a template placeholder that renders to nothing, an
    absent `WHERE` among them, would otherwise leave a line of spaces behind.

    Returns:
        str: The fragment, re-indented to column zero.

    """

    lines = [line.rstrip() for line in dedent(sql).splitlines()]

    return "\n".join(line for line in lines if line.strip())


########################################################################################


def consume_quoted(
    *,
    buffer: list[str],
    start: int,
    sql: str,
    quote_char: str,
) -> int:
    """
    Copy a quoted run into the buffer, honouring doubled-quote escapes.

    Returns:
        int: The index just past the closing quote.

    """

    end = start + 1

    length = len(sql)

    while end < length:
        if sql[end] != quote_char:
            end += 1
        elif (end + 1) < length and sql[end + 1] == quote_char:
            end += 2
        else:
            end += 1
            break

    buffer.append(sql[start:end])

    return end


def split_statements(sql: str) -> list[str]:
    """
    Split a SQL script into individually executable statements.

    Aware of string literals with `''` escapes, quoted identifiers,
    dollar-quoted bodies, and both comment styles, all of which show up in
    trigger function definitions and all of which can contain a bare `;`.

    Drivers that use the extended query protocol, `asyncpg` among them, reject
    more than one command per execution, and Alembic's `--sql` mode wants one
    statement per line. Installing a trigger is inherently several statements,
    so everything is split before it is run.

    Returns:
        list[str]: The statements, stripped, with empties dropped.

    """

    statements: list[str] = []
    buffer: list[str] = []
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]

        if char in {"'", '"'}:
            index = consume_quoted(
                buffer=buffer,
                start=index,
                sql=sql,
                quote_char=char,
            )
        elif char == "$" and (match := DOLLAR_TAG_PATTERN.match(sql, index)):
            tag = match.group(0)
            close = sql.find(tag, match.end())
            end = length if close == -1 else close + len(tag)
            buffer.append(sql[index:end])
            index = end
        elif sql.startswith("--", index):
            end = sql.find("\n", index)
            end = length if end == -1 else end
            buffer.append(sql[index:end])
            index = end
        elif sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            end = length if end == -1 else end + 2
            buffer.append(sql[index:end])
            index = end
        elif char == ";":
            statements.append("".join(buffer))
            buffer = []
            index += 1
        else:
            buffer.append(char)
            index += 1

    statements.append("".join(buffer))

    return [statement.strip() for statement in statements if statement.strip()]
