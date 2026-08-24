"""
The rows a trigger can see, and the names they render under.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from sqlalchemy import literal_column, quoted_name

from pgtrigger.enums import TransitionTable

if TYPE_CHECKING:
    from typing import Final

    from sqlalchemy import ColumnElement, Table
    from sqlalchemy.sql.base import ReadOnlyColumnCollection

    from .clauses import Referencing

########################################################################################


@final
class RowProxy:
    """
    Attribute access onto one of the rows visible inside a trigger.

    Wraps the table in an alias named `OLD`, `NEW`, or a transition table, so
    that ordinary SQLAlchemy expressions render with the right prefix:

    ```python
    old(orders).status.is_distinct_from(new(orders).status)
    ```

    `old.status` and `old.c.status` are equivalent; the second form is there for
    columns whose name collides with an attribute of this class.
    """

    __slots__ = ("alias", "selectable", "table")

    def __init__(self, alias: str, table: Table) -> None:
        """
        Alias the table under the given row name.
        """

        self.alias = str(alias)
        self.table = table

        # quote=False keeps the alias rendering as a bare OLD/NEW rather than quoted,
        # which PostgreSQL will not accept in a trigger condition
        self.selectable = table.alias(quoted_name(self.alias, quote=False))

    def __getattr__(self, name: str) -> ColumnElement:
        """
        Look a column up by ORM attribute name.

        Returns:
            ColumnElement: The aliased column.

        Raises:
            AttributeError: No such column on the table.

        """

        if name.startswith("_"):
            raise AttributeError(name)

        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f'"{name}" is not a column on table "{self.table.name}".'
                f" Available: {sorted(c.key for c in self.table.columns)}"
            ) from None

    def __getitem__(self, name: str) -> ColumnElement:
        """
        Look a column up by ORM attribute name, then by database name.

        Returns:
            ColumnElement: The aliased column.

        Raises:
            KeyError: No such column on the table.

        """

        column = self.selectable.c.get(name)

        if column is not None:
            return column

        for candidate in self.selectable.c:
            if candidate.name == name:
                return candidate

        raise KeyError(name)

    def __repr__(self) -> str:
        """
        Show the row name and its table.

        Returns:
            str: A short representation.

        """

        return f"<{self.alias} {self.table.name}>"

    @property
    def all(self) -> ColumnElement:
        """
        Reference the whole row, `OLD.*` or `NEW.*`.

        PostgreSQL compares entire rows with `IS DISTINCT FROM`, which is cheaper
        than testing each column and is what a bare `AnyChange()` compiles to.

        Returns:
            ColumnElement: The whole-row reference.

        """

        return literal_column(f"{self.alias}.*")

    @property
    def c(self) -> ReadOnlyColumnCollection:
        """
        Expose the aliased column collection.

        Returns:
            ReadOnlyColumnCollection: The columns of this row.

        """

        return self.selectable.c

    @property
    def columns(self) -> ReadOnlyColumnCollection:
        """
        Expose the aliased column collection.

        Returns:
            ReadOnlyColumnCollection: The columns of this row.

        """

        return self.selectable.c


########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
@final
class RowScope:
    """
    The rows a condition resolves against.

    A row-level condition compares `OLD` to `NEW`.
    The same condition on statement-level triggers needs transition tables instead,
    since `OLD` and `NEW` do not exist there. Rather than resolve against `OLD`/`NEW`
    and rewrite the resulting SQL, the aliases are chosen up front and the
    expression language renders the right names the first time.
    """

    table: Table

    old_alias: Final[str] = TransitionTable.OLD
    new_alias: Final[str] = TransitionTable.NEW

    @classmethod
    def transitions(cls, referencing: Referencing, table: Table) -> RowScope:
        """
        Build a scope naming a statement-level trigger's transition tables.

        Either side may be absent, in which case its alias falls back to
        `OLD`/`NEW`. Referencing the missing side then renders SQL PostgreSQL
        rejects, which is what the caller's validation is for.

        Returns:
            Scope: A scope over the transition tables.

        """

        return cls(
            table=table,
            old_alias=(referencing.old or TransitionTable.OLD),
            new_alias=(referencing.new or TransitionTable.NEW),
        )

    @property
    def new(self) -> RowProxy:
        """
        Proxy the row as it will be.

        Returns:
            RowProxy: Proxy onto the new row.

        """

        return RowProxy(self.new_alias, self.table)

    @property
    def old(self) -> RowProxy:
        """
        Proxy the row as it was.

        Returns:
            RowProxy: Proxy onto the old row.

        """

        return RowProxy(self.old_alias, self.table)


########################################################################################


def new(table: Table) -> RowProxy:
    """
    Build the `NEW` row proxy for a table.

    Returns:
        RowProxy: Proxy onto the row a statement is writing.

    """

    return RowProxy(TransitionTable.NEW, table)


def old(table: Table) -> RowProxy:
    """
    Build the `OLD` row proxy for a table.

    Returns:
        RowProxy: Proxy onto the row a statement is replacing or removing.

    """

    return RowProxy(TransitionTable.OLD, table)
