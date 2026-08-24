"""
Altering a column a trigger depends on.
"""

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pgtrigger.ddl

from pgtrigger.utils import quote

from .reflection import reflect

if TYPE_CHECKING:
    from collections.abc import Generator

    from alembic.operations import Operations

########################################################################################


@contextmanager
def temporarily_drop_triggers(
    operations: Operations,
    table: str,
    schema: str | None = None,
) -> Generator[None]:
    """
    Drop a table's managed triggers, run the block, then put them back.

    Postgres refuses to alter the type of a column named in a trigger's `WHEN`
    clause. Since revisions are meant to be read and edited, the workaround is
    explicit rather than hidden behind an error handler:

    ```python
    def upgrade() -> None:
        with pgtrigger.migrations.temporarily_drop_triggers(op, "orders"):
            op.alter_column("orders", "status", type_=sa.String(64))
    ```

    Triggers are restored from `pg_get_triggerdef`, comment included, so
    autogenerate will not report drift afterwards.

    Yields:
        Generator: A context manager.

    Raises:
        RuntimeError: Called in `--sql` mode, where there is no connection to
                      reflect from.

    """

    if operations.migration_context.as_sql:
        raise RuntimeError(
            "temporarily_drop_triggers() needs a live connection to read the"
            " existing triggers, so it cannot run in --sql mode."
        )

    connection = operations.get_bind()
    resolved = schema or connection.dialect.default_schema_name or "public"
    qualified = f"{quote(resolved)}.{quote(table)}"

    existing = [
        item
        for item in reflect(connection)
        if item.table == table and item.schema == resolved
    ]

    for item in existing:
        pgtrigger.ddl.execute(
            connection,
            f"DROP TRIGGER IF EXISTS {item.pgid} ON {qualified};",
        )

    try:
        yield
    finally:
        for item in existing:
            pgtrigger.ddl.execute(connection, item.restore_sql)
