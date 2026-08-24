"""
Removing a trigger.
"""

from dataclasses import dataclass
from typing import final, override

from pgtrigger.core import Statement

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class Drop(Statement):
    """
    Removes a trigger, leaving the function behind it in place.

    `IF EXISTS`, so uninstalling twice is not an error and a migration can be
    re-run against a database that has already moved on.
    """

    pgid: str
    table: str

    @property
    @override
    def sql(self) -> str:
        """
        Render the statement.

        Returns:
            str: A `DROP TRIGGER` statement.

        """

        return f"DROP TRIGGER IF EXISTS {self.pgid} ON {self.table};"
