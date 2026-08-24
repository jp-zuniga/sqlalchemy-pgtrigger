"""
Teaching autogenerate to notice triggers.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from alembic.autogenerate import comparators

import pgtrigger.registry

from pgtrigger.config import CONFIG
from pgtrigger.utils import quote

from .operations import CreatePGTriggerOp, DropPGTriggerOp
from .reflection import reflect

if TYPE_CHECKING:
    from collections.abc import Sequence

    from alembic.autogenerate.api import AutogenContext
    from alembic.operations.ops import UpgradeOps
    from sqlalchemy import MetaData


########################################################################################


@runtime_checkable
class IncludeTrigger(Protocol):
    """
    Filter passed to Alembic's context as `include_pgtrigger`.

    Called as `(table, name, action)` where `action` is `"create"` or `"drop"`.
    Return false to leave that trigger alone.
    """

    def __call__(self, table: str, name: str, action: str) -> bool:
        """
        Decide whether to consider a trigger.

        Returns:
            bool: `True` to include it in the diff.

        """


########################################################################################


def metadatas(autogen_context: AutogenContext) -> list[MetaData]:
    """
    Collect the `MetaData` objects this run was handed.

    Returns:
        list[MetaData]: Zero or more `MetaData`.

    """

    metadata = autogen_context.metadata

    if metadata is None:
        return []

    if isinstance(metadata, Iterable):
        return list(metadata)

    return [metadata]


def in_scope(schema: str, default: str, schemas: Sequence[str | None]) -> bool:
    """
    Decide whether autogenerate was asked to look at this schema.

    Returns:
        bool: `True` if the schema is in scope.

    """

    if not schemas:
        return schema == default

    return schema in schemas or (schema == default and None in schemas)


########################################################################################


@comparators.dispatch_for("schema")
def compare_pgtriggers(
    autogen_context: AutogenContext,
    upgrade_ops: UpgradeOps,
    schemas: Sequence[str | None],
) -> None:
    """
    Diff declared triggers against what is installed.
    """

    connection = autogen_context.connection

    if connection is None or connection.dialect.name != "postgresql":
        return

    include: IncludeTrigger | None = autogen_context.opts.get("include_pgtrigger")

    default = connection.dialect.default_schema_name or "public"

    known = metadatas(autogen_context)

    declared = {
        (r.table.schema or default, r.table.name, r.pgid): r
        for r in pgtrigger.registry.for_metadata(*known)
    }

    reflected = {
        item.key: item
        for item in reflect(connection)
        if in_scope(item.schema, default, schemas)
    }

    # tables this metadata knows about;
    # one that has gone entirely gets a drop_table,
    # which takes its triggers with it
    known_tables: set[tuple[str, str]] = {
        (table.schema or default, table.name)
        for metadata in known
        for table in metadata.tables.values()
    }

    known_tables.update((schema, table) for schema, table, _ in declared)

    capture = CONFIG.autogenerate_reverse_sql

    for key, registration in sorted(declared.items()):
        name = registration.trigger.name

        if include is not None and not include(registration.table.name, name, "create"):
            continue

        compiled = registration.compile()
        existing = reflected.get(key)

        if existing is not None and existing.fingerprint == compiled.fingerprint:
            continue

        upgrade_ops.ops.append(
            CreatePGTriggerOp(
                pgid=compiled.pgid,
                table=compiled.table,
                sql=compiled.install_sql,
                fingerprint=compiled.fingerprint,
                reverse_sql=(
                    existing.restore_sql if existing is not None and capture else None
                ),
            )
        )

    for key, existing in sorted(reflected.items()):
        if key in declared or (existing.schema, existing.table) not in known_tables:
            continue

        if include is not None and not include(existing.table, existing.pgid, "drop"):
            continue

        # qualify only outside the default schema,
        # so the common case renders as a plain table name
        table_ref = (
            quote(existing.table)
            if existing.schema == default
            else f"{quote(existing.schema)}.{quote(existing.table)}"
        )

        upgrade_ops.ops.append(
            DropPGTriggerOp(
                pgid=existing.pgid,
                table=table_ref,
                reverse_sql=existing.restore_sql if capture else None,
            )
        )
