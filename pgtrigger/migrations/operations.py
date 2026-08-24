"""
The operations a revision can call.
"""

from typing import TYPE_CHECKING, override

from alembic.operations import MigrateOperation, Operations

import pgtrigger.ddl

if TYPE_CHECKING:
    from pgtrigger.aliases import Executor

########################################################################################


def emit(operations: Operations, sql: str) -> None:
    """
    Run a script a statement at a time, honouring `--sql` mode.

    Offline output goes through the migration context's own implementation
    rather than `operations.impl`, which is a batch implementation inside a
    `batch_alter_table` block and has no `static_output`.
    """

    context = operations.migration_context

    if context.as_sql:
        for statement in pgtrigger.ddl.statements(sql):
            context.impl.static_output(f"{statement};\n")
    else:
        executor: Executor = operations.get_bind()
        pgtrigger.ddl.execute(executor, sql)


########################################################################################


@Operations.register_operation("create_pgtrigger")
class CreatePGTriggerOp(MigrateOperation):
    """
    Create or replace a trigger and the function behind it.

    Carries the SQL itself. `pgid`, `table`, and `fingerprint` are along for
    identification and for the reverse operation.
    """

    def __init__(
        self,
        *,
        pgid: str,
        table: str,
        sql: str,
        fingerprint: str = "",
        reverse_sql: str | None = None,
    ) -> None:
        """
        Store the trigger's identity and the SQL that installs it.
        """

        self.pgid = pgid
        self.table = table
        self.sql = sql
        self.fingerprint = fingerprint
        self.reverse_sql = reverse_sql

    @classmethod
    def create_pgtrigger(  # ruff: ignore[too-many-arguments]
        cls,
        operations: Operations,
        *,
        pgid: str,
        table: str,
        sql: str,
        fingerprint: str = "",
        reverse_sql: str | None = None,
    ) -> None:
        """
        Create or replace a trigger.
        """

        operations.invoke(
            cls(
                pgid=pgid,
                table=table,
                sql=sql,
                fingerprint=fingerprint,
                reverse_sql=reverse_sql,
            )
        )

    @override
    def reverse(self) -> MigrateOperation:
        """
        Put back whatever was there before.

        Returns:
            MigrateOperation: A restore if one was captured, otherwise a drop.

        """

        if self.reverse_sql:
            return RunPGSQLOp(sql=self.reverse_sql)

        return DropPGTriggerOp(pgid=self.pgid, table=self.table)


########################################################################################


@Operations.register_operation("drop_pgtrigger")
class DropPGTriggerOp(MigrateOperation):
    """
    Drop a trigger by its Postgres identifier.
    """

    def __init__(
        self,
        *,
        pgid: str,
        table: str,
        reverse_sql: str | None = None,
    ) -> None:
        """
        Store the trigger's identity and how to put it back.
        """

        self.pgid = pgid
        self.table = table
        self.reverse_sql = reverse_sql

    @classmethod
    def drop_pgtrigger(
        cls,
        operations: Operations,
        *,
        pgid: str,
        table: str,
        reverse_sql: str | None = None,
    ) -> None:
        """
        Drop a trigger.
        """

        operations.invoke(cls(pgid=pgid, table=table, reverse_sql=reverse_sql))

    @override
    def reverse(self) -> MigrateOperation:
        """
        Put the trigger back.

        Returns:
            MigrateOperation: The captured restore.

        Raises:
            NotImplementedError: Nothing was captured to restore from.

        """

        if self.reverse_sql:
            return RunPGSQLOp(sql=self.reverse_sql)

        raise NotImplementedError(
            f'Cannot reverse dropping trigger "{self.pgid}": no reverse SQL was'
            " captured. Pass reverse_sql= or write the downgrade by hand."
        )


########################################################################################


@Operations.register_operation("run_pgsql")
class RunPGSQLOp(MigrateOperation):
    """
    Run raw SQL with no bind parameters.

    Use this rather than `op.execute()` for anything containing `%`
    or a dollar-quoted body: it splits statements and keeps the driver
    from trying to interpolate.
    """

    def __init__(self, *, sql: str, reverse_sql: str | None = None) -> None:
        """
        Store the script and its reverse.
        """

        self.sql = sql
        self.reverse_sql = reverse_sql

    @classmethod
    def run_pgsql(
        cls,
        operations: Operations,
        *,
        sql: str,
        reverse_sql: str | None = None,
    ) -> None:
        """
        Run raw SQL.
        """

        operations.invoke(cls(sql=sql, reverse_sql=reverse_sql))

    @override
    def reverse(self) -> MigrateOperation:
        """
        Run the other direction.

        Returns:
            MigrateOperation: The reverse script.

        Raises:
            NotImplementedError: No reverse script was given.

        """

        if self.reverse_sql:
            return RunPGSQLOp(sql=self.reverse_sql)

        raise NotImplementedError("run_pg_sql() was given no reverse_sql.")


########################################################################################


@Operations.implementation_for(CreatePGTriggerOp)
def create_pgtrigger(operations: Operations, operation: CreatePGTriggerOp) -> None:
    """
    Run a `CreatePGTriggerOp`.
    """

    emit(operations, operation.sql)


@Operations.implementation_for(DropPGTriggerOp)
def drop_pgtrigger(operations: Operations, operation: DropPGTriggerOp) -> None:
    """
    Run a `DropPGTriggerOp`.
    """

    # the table reference arrives quoted, from CompiledTrigger.table or from
    # the comparator, so quoting it again would nest the quotes
    emit(
        operations,
        f"DROP TRIGGER IF EXISTS {operation.pgid} ON {operation.table};",
    )


@Operations.implementation_for(RunPGSQLOp)
def run_pgsql(operations: Operations, operation: RunPGSQLOp) -> None:
    """
    Run a `RunPGSQLOp`.
    """

    emit(operations, operation.sql)
