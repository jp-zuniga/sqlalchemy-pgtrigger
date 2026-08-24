"""
Re-arming a trigger.
"""

from dataclasses import dataclass
from typing import final, override

from pgtrigger.core import Statement

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class Enable(Statement):
    """
    Re-arms a trigger that was disabled.

    Takes an `ACCESS EXCLUSIVE` lock on the table for the duration.
    """

    pgid: str
    table: str

    @property
    @override
    def sql(self) -> str:
        """
        Render the statement.

        Returns:
            str: An `ALTER TABLE ... ENABLE TRIGGER` statement.

        """

        return f"ALTER TABLE {self.table} ENABLE TRIGGER {self.pgid};"
