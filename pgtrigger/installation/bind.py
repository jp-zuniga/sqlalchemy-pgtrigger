"""
Turning a connectable into something that can run a statement.
"""

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import Connection, Engine

if TYPE_CHECKING:
    from collections.abc import Generator

    from pgtrigger.aliases import Connectable, Executor

#######################################################################################


@contextmanager
def bind(connectable: Connectable) -> Generator[Executor]:
    """
    Yield something with an `execute()`, opening a transaction if needed.

    Yields:
        Generator[Executor]: The executor to use.

    Raises:
        TypeError: The argument cannot run SQL.

    """

    if isinstance(connectable, Engine):
        with connectable.begin() as connection:
            yield connection

        return

    if isinstance(connectable, Connection) or hasattr(connectable, "execute"):
        yield connectable

        return

    raise TypeError(
        f"Expected an Engine, Connection, or Session; got {type(connectable).__name__}."
    )


#######################################################################################


def default_schema(executor: Executor) -> str:
    """
    Report the schema an unqualified table resolves to on this connection.

    Returns:
        str: The default schema name.

    """

    if isinstance(executor, Connection):
        dialect = executor.dialect
    else:
        dialect = executor.get_bind().dialect

    return dialect.default_schema_name or "public"
