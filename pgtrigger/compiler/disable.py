"""
Standing a trigger down for everyone.
"""

from dataclasses import dataclass
from typing import final, override

from pgtrigger.core import Statement

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class Disable(Statement):
    """
    Leaves a trigger installed but stops it firing, for everyone.

    Persistent and connection-independent. To stand a trigger down for one
    block of code, use `pgtrigger.ignore` instead.
    """

    pgid: str
    table: str

    @property
    @override
    def sql(self) -> str:
        """
        Render the statement.

        Returns:
            str: An `ALTER TABLE ... DISABLE TRIGGER` statement.

        """

        return f"ALTER TABLE {self.table} DISABLE TRIGGER {self.pgid};"
