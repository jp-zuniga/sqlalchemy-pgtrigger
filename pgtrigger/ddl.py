"""
Getting trigger SQL into the database.

Two things make this less trivial than it looks.

## Percent signs

Trigger bodies contain `%`, from `RAISE EXCEPTION '... %'`.
SQLAlchemy executes DDL with an empty parameter mapping rather than no parameters,
so `psycopg` still runs the statement through `%`-interpolation and a lone `%` raises.
Stock `sqlalchemy.schema.DDL` avoids this by routing its text through the compiler's
`post_process_text`, which doubles percent signs for the `format` and `pyformat`
paramstyles and leaves them alone otherwise. `RawSQL` does the same,
so it inherits the behaviour rather than guessing at it.

## Multiple statements

Installing a trigger means creating a function, recreating the trigger,
and commenting on it. Drivers using the extended query protocol reject more
than one command per execution, so scripts are split and run a statement at a time.
"""

from typing import TYPE_CHECKING

from sqlalchemy import event
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import ExecutableDDLElement

import pgtrigger.registry

from pgtrigger.config import CONFIG
from pgtrigger.consts import LISTENER_KEY
from pgtrigger.utils import split_statements

if TYPE_CHECKING:
    from sqlalchemy import Connection, Table
    from sqlalchemy.sql.compiler import DDLCompiler

    from pgtrigger.aliases import Executor

########################################################################################


class RawSQL(ExecutableDDLElement):
    """
    One SQL statement, executed with DDL semantics and no bind parameters.

    Use this, not `text()`, for anything containing `%` or a dollar-quoted body.
    """

    def __init__(self, sql: str) -> None:
        """
        Store the statement.
        """

        self.sql = sql

    def __repr__(self) -> str:
        """
        Show the statement.

        Returns:
            str: A reconstructable representation.

        """

        return f"RawSQL({self.sql!r})"

    def __str__(self) -> str:
        """
        Render the statement.

        Returns:
            str: The SQL as given.

        """

        return self.sql


@compiles(RawSQL)
def compile_raw_sql(element: RawSQL, compiler: DDLCompiler, **kwargs: object) -> str:  # ruff: ignore[unused-function-argument]
    """
    Hand the statement to the compiler's own text post-processing.

    Returns:
        str: The statement, escaped as the active paramstyle requires.

    """

    return compiler.sql_compiler.post_process_text(element.sql)


########################################################################################


def execute(executor: Executor, sql: str) -> None:
    """
    Run a script, one statement at a time.
    """

    for statement in statements(sql):
        executor.execute(RawSQL(statement))


def statements(sql: str) -> list[str]:
    """
    Split a script into individually executable statements.

    Returns:
        list[str]: The statements, in order.

    """

    return split_statements(sql)


########################################################################################


def attach(table: Table) -> None:
    """
    Arrange for a table's triggers to be installed by `create_all()`.

    One listener serves the whole table however many triggers it has, and it
    reads the registry when it fires rather than closing over what was declared
    at the time, so a trigger attached later is still installed.

    Both the dialect check and the config check happen at execution time, so the
    same models can be created against SQLite in a test suite without emitting
    PostgreSQL DDL.
    """

    if table.info.get(LISTENER_KEY):
        return

    table.info[LISTENER_KEY] = True

    def after_create(target: Table, connection: Connection, **kwargs: object) -> None:  # ruff: ignore[unused-function-argument]
        if connection.dialect.name != "postgresql" or not CONFIG.install_on_create:
            return

        for registration in pgtrigger.registry.for_table(target):
            execute(connection, registration.compile().install_sql)

    event.listen(table, "after_create", after_create)
