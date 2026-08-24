"""
What the registry stores.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pgtrigger.utils import table_uri

if TYPE_CHECKING:
    from sqlalchemy import Table

    from pgtrigger.compiler import CompiledTrigger
    from pgtrigger.core import Trigger

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
class RegistryEntry:
    """
    A trigger together with the table it was declared on.

    Pairing them saves every caller from carrying two values around,
    and gives the derived identifiers (the URI, the PostgreSQL identifier,
    the compiled SQL) somewhere to live.
    """

    table: Table
    trigger: Trigger

    def __str__(self) -> str:
        """
        Name the registration.

        Returns:
            str: The trigger URI.

        """

        return self.uri

    def compile(self) -> CompiledTrigger:
        """
        Reduce the declaration to SQL.

        Returns:
            CompiledTrigger: The installable form.

        """

        return self.trigger.compile(self.table)

    @property
    def pgid(self) -> str:
        """
        Read the identifier the trigger carries in PostgreSQL.

        Returns:
            str: The PostgreSQL identifier.

        """

        return self.trigger.pgid(self.table)

    @property
    def table_uri(self) -> str:
        """
        Read the table portion of the URI, `<schema>.table`.

        Returns:
            str: The table reference, unquoted.

        """

        return table_uri(self.table)

    @property
    def uri(self) -> str:
        """
        Read how this trigger is named to the registry and to users.

        Returns:
            str: The trigger URI.

        """

        return self.trigger.uri(self.table)
