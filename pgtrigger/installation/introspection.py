"""
Reading managed triggers back out of the database.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

import pgtrigger.registry

from pgtrigger.compiler import parse_comment
from pgtrigger.consts import INSTALLED_SQL
from pgtrigger.utils import quote

from .bind import bind, default_schema

if TYPE_CHECKING:
    from pgtrigger.aliases import Connectable

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
class InstalledTrigger:
    """
    A managed trigger found in the database.
    """

    schema: str
    table: str
    pgid: str
    enabled: bool

    version: int | None
    """
    Template version from the trigger's comment, or `None` if unreadable.
    """

    fingerprint: str | None
    """
    Digest from the trigger's comment, or `None` if unreadable.
    """

    def __str__(self) -> str:
        """
        Name the trigger and the table it sits on.

        Returns:
            str: A qualified reference.

        """

        return f"{self.qualified_table}.{self.pgid}"

    @property
    def key(self) -> tuple[str, str, str]:
        """
        Identify this trigger within the database.

        Returns:
            tuple[str, str, str]: Schema, table, and identifier.

        """

        return (self.schema, self.table, self.pgid)

    @property
    def qualified_table(self) -> str:
        """
        Quote the table, schema included.

        Returns:
            str: The table reference.

        """

        return f"{quote(self.schema)}.{quote(self.table)}"


########################################################################################


def installed(connectable: Connectable) -> list[InstalledTrigger]:
    """
    List every managed trigger present in the database.

    Nothing without our identifier prefix comes back,
    so a hand-written trigger is invisible here and
    safe from everything else in this package.

    Returns:
        list[InstalledTrigger]: What is actually installed.

    """

    with bind(connectable) as executor:
        rows = executor.execute(text(INSTALLED_SQL)).fetchall()

    results: list[InstalledTrigger] = []

    for schema, table, pgid, comment, enabled in rows:
        version, fingerprint = parse_comment(comment) or (None, None)

        results.append(
            InstalledTrigger(
                schema=schema,
                table=table,
                pgid=pgid,
                enabled=(enabled == "O"),  # 'O' is armed, 'D' is disabled
                version=version,
                fingerprint=fingerprint,
            )
        )

    return results


########################################################################################


def prunable(connectable: Connectable) -> list[InstalledTrigger]:
    """
    List managed triggers in the database that no longer have a declaration.

    Returns:
        list[InstalledTrigger]: What `prune` would drop.

    """

    with bind(connectable) as executor:
        schema = default_schema(executor)
        declared = {
            (r.table.schema or schema, r.table.name, r.pgid)
            for r in pgtrigger.registry.iterate()
        }

        return [
            trigger for trigger in installed(executor) if trigger.key not in declared
        ]
