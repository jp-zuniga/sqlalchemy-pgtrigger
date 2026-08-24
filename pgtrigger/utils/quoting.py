"""
Rendering identifiers and literals the way PostgreSQL reads them.
"""

from typing import TYPE_CHECKING

from pgtrigger.consts import PREPARER

if TYPE_CHECKING:
    from sqlalchemy import Column, Table

########################################################################################


def quote(name: str) -> str:
    """
    Quote an identifier if PostgreSQL would not read it as written.

    Lower-case identifiers that are not reserved words pass through unquoted,
    which keeps generated SQL readable.

    Returns:
        str: The identifier, quoted if it needs to be.

    """

    return PREPARER.quote(name)


########################################################################################


def quote_column(column: Column) -> str:
    """
    Quote a column name, without a table prefix.

    Returns:
        str: The column reference.

    """

    return PREPARER.format_column(column)


########################################################################################


def quote_literal(value: str) -> str:
    """
    Render a Python string as a PostgreSQL string literal.

    Returns:
        str: The quoted literal, with embedded quotes doubled.

    """

    escaped = value.replace("'", "''")

    return f"'{escaped}'"


########################################################################################


def quote_table(table: Table) -> str:
    """
    Quote a table, including its schema when it has one.

    Returns:
        str: The table reference.

    """

    return PREPARER.format_table(table)
