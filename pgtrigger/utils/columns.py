"""
Resolving names to the columns they mean.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy import Table

########################################################################################


def pk_columns(table: Table) -> list[Column]:
    """
    Collect a table's primary key columns, composite keys included.

    Returns:
        list[Column]: The primary key columns, in order.

    Raises:
        ValueError: The table has no primary key.

    """

    columns = list(table.primary_key.columns)

    if not columns:
        raise ValueError(
            f'Table "{table.name}" has no primary key, which this trigger requires.'
        )

    return columns


########################################################################################


def resolve_column(field: str | Column, table: Table) -> Column:
    """
    Resolve an ORM attribute name or database column name to a `Column`.

    Returns:
        Column: The matching column.

    Raises:
        ValueError: Nothing on the table matches.

    """

    if isinstance(field, Column):
        return field

    column = table.columns.get(field)

    if column is not None:
        return column

    for candidate in table.columns:
        if candidate.name == field:
            return candidate

    raise ValueError(
        f'Field "{field}" does not resolve to a column on table "{table.name}".'
        f" Available: {sorted(c.key for c in table.columns)}"
    )


def resolve_columns(fields: Iterable[str | Column], table: Table) -> list[Column]:
    """
    Resolve several names at once.

    Returns:
        list[Column]: The matching columns, in the order given.

    Raises:
        ValueError: One of the names matches nothing on the table.

    """  # ruff: ignore[docstring-extraneous-exception]

    return [resolve_column(field, table) for field in fields]
