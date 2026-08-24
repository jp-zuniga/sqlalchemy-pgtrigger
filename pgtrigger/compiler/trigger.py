"""
A declaration reduced to SQL.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .disable import Disable
from .drop import Drop
from .enable import Enable

if TYPE_CHECKING:
    from .upsert import Upsert

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
class CompiledTrigger:
    """
    A declaration reduced to SQL.

    This is what installation runs and what autogenerate compares. It holds no
    reference back to the `Trigger` that produced it, or to the table, so
    nothing it emits can shift underneath a migration that has already been
    written.
    """

    name: str
    """
    The trigger's declared name, as written by the user.
    """

    upsert: Upsert
    """
    The statements that create the trigger and its function.
    """

    def __str__(self) -> str:
        """
        Render the installation script.

        Returns:
            str: Several statements.

        """

        return self.install_sql

    @property
    def comment(self) -> str:
        """
        Read the comment written onto the installed trigger.

        Returns:
            str: The marker recording the template version and fingerprint.

        """

        return self.upsert.comment

    @property
    def disable_sql(self) -> str:
        """
        Render the statement that stops the trigger firing.

        Returns:
            str: A single statement.

        """

        return Disable(pgid=self.pgid, table=self.table).sql

    @property
    def enable_sql(self) -> str:
        """
        Render the statement that re-arms the trigger.

        Returns:
            str: A single statement.

        """

        return Enable(pgid=self.pgid, table=self.table).sql

    @property
    def fingerprint(self) -> str:
        """
        Read the digest of the trigger definition.

        Returns:
            str: A hex digest.

        """

        return self.upsert.fingerprint

    @property
    def install_sql(self) -> str:
        """
        Render the script that creates or replaces the trigger.

        Returns:
            str: Several statements.

        """

        return self.upsert.sql

    @property
    def pgid(self) -> str:
        """
        Read the trigger's PostgreSQL identifier.

        Returns:
            str: The generated identifier.

        """

        return self.upsert.pgid

    @property
    def table(self) -> str:
        """
        Read the quoted table the trigger is attached to.

        Returns:
            str: The table reference.

        """

        return self.upsert.table

    @property
    def uninstall_sql(self) -> str:
        """
        Render the statement that removes the trigger.

        Returns:
            str: A single statement.

        """

        return Drop(pgid=self.pgid, table=self.table).sql
