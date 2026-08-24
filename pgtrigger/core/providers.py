"""
Base classes for the things that render into trigger SQL.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy import Table

########################################################################################


@runtime_checkable
class Renderable(Protocol):
    """
    Anything that can turn itself into a fragment of trigger SQL.

    A clause is rendered late, against the table it was declared on,
    because `__table_args__` is evaluated before the table exists.

    This is a `Protocol` rather than a `ABC` so that `StrEnum` clauses can satisfy it.
    An enum cannot inherit from an `ABC` because of conflicting metaclasses.
    """

    __slots__ = ()

    def render(self, table: Table) -> str:
        """
        Render this clause against a table.

        Returns:
            str: The SQL fragment.

        """


########################################################################################


class Clause(ABC):
    """
    Base for clauses that are ordinary classes rather than enums.

    Deliberately without a `__str__`.

    Some clauses cannot render without a table,
    and a `__str__` quietly producing something other than `render()` would be a trap.
    """

    __slots__ = ()

    @abstractmethod
    def render(self, table: Table) -> str:
        """
        Render this clause against a table.

        Returns:
            str: The SQL fragment.

        """


########################################################################################


class Statement(ABC):
    """
    Base for a complete, standalone SQL statement.

    Unlike a `Clause`, a statement needs no table to render:
    by the time one is built, every identifier has already been resolved and quoted.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def sql(self) -> str:
        """
        Render the statement.

        Returns:
            str: SQL, terminated with a semicolon.

        """

    def __str__(self) -> str:
        """
        Render the statement.

        Returns:
            str: SQL, terminated with a semicolon.

        """

        return self.sql
