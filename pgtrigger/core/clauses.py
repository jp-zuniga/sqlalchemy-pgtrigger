"""
The clauses of a `CREATE TRIGGER` statement.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, final, override

from pgtrigger.enums import LogicalOperator
from pgtrigger.utils import quote_column, resolve_columns

from .providers import Clause, Renderable

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from sqlalchemy import Table

    from pgtrigger.aliases import EventClause


########################################################################################


@final
class ForEach(StrEnum):
    """
    Values of a trigger's `FOR EACH` clause.

    A row-level trigger fires once per affected row;
    a statement-level trigger fires once per statement, however many rows it touched.
    """

    ROW = "ROW"
    STATEMENT = "STATEMENT"


########################################################################################


@final
class Time(StrEnum):
    """
    When a trigger fires relative to the statement.
    """

    AFTER = "AFTER"
    BEFORE = "BEFORE"
    INSTEAD_OF = "INSTEAD OF"
    """
    Replaces the operation entirely. Only valid on views, and only row-level.
    """


########################################################################################


@final
class Execution(StrEnum):
    """
    Values of a trigger's deferrability clause.

    Anything other than `NOT_DEFERRABLE` makes this a constraint trigger,
    whose firing can be postponed to the end of the transaction.

    The member value is the bare word `SET CONSTRAINTS` expects;
    `clause` is the longer form that belongs in `CREATE TRIGGER`.
    """

    DEFERRED = "DEFERRED"
    IMMEDIATE = "IMMEDIATE"
    NOT_DEFERRABLE = "NOT DEFERRABLE"

    @property
    def clause(self) -> str:
        """
        Render the value as it appears in `CREATE TRIGGER`.

        Returns:
            str: The deferrability clause.

        """

        if self is Execution.NOT_DEFERRABLE:
            return self.value

        return f"DEFERRABLE INITIALLY {self.value}"

    @property
    def deferrable(self) -> bool:
        """
        Report whether this makes the trigger a constraint trigger.

        Returns:
            bool: `True` for anything but `NOT_DEFERRABLE`.

        """

        return self is not Execution.NOT_DEFERRABLE


########################################################################################


@final
class Event(StrEnum):
    """
    A single operation a trigger fires on.

    Combine with `|`:

    ```python
    events=(pgtrigger.Event.UPDATE | pgtrigger.Event.DELETE)
    ```
    """

    DELETE = "DELETE"
    INSERT = "INSERT"
    TRUNCATE = "TRUNCATE"
    UPDATE = "UPDATE"

    def __or__(self, other: EventClause) -> Events:
        """
        Combine this event with another.

        Returns:
            Events: The combined event list.

        """

        return Events(self, other)

    @property
    def base_events(self) -> frozenset[Event]:
        """
        Report the plain events this clause covers.

        Returns:
            frozenset[Event]: A set holding just this member.

        """

        return frozenset({self})

    def render(self, table: Table) -> str:  # ruff: ignore[unused-method-argument]
        """
        Render this event.

        Returns:
            str: The event keyword.

        """

        return self.value


########################################################################################


@final
class Events(Clause):
    """
    Several events `OR`-ed together.

    Built with `|` rather than directly.

    Nested groups flatten and duplicates drop, so `A | B | A` is `A | B`.
    """

    __slots__ = ("events",)

    def __init__(self, *events: EventClause) -> None:
        """
        Flatten, de-duplicate, and store the events.

        Raises:
            TypeError: Something that is not an event was combined in.
            ValueError: No events were given.

        """

        flattened: list[Event | UpdateOf] = []

        for event in events:
            match event:
                case Events():
                    candidates: Sequence[Event | UpdateOf] = event.events
                case Event() | UpdateOf():
                    candidates = (event,)
                case _:
                    raise TypeError(
                        f"Cannot combine {type(event).__name__} "
                        "into a trigger event list."
                    )

            # de-duplicate over the flattened contents, not the operands,
            # so that `Events(A, B) | Events(B, C)` keeps one `B`
            flattened.extend(c for c in candidates if c not in flattened)

        if not flattened:
            raise ValueError("Must provide at least one event.")

        self.events: Sequence[Event | UpdateOf] = tuple(flattened)

    def __contains__(self, other: object) -> bool:
        """
        Test whether an event is in this list.

        Returns:
            bool: `True` when the event is a member.

        """

        return other in self.events

    def __eq__(self, other: object) -> bool:
        """
        Compare two event lists by their members and order.

        Returns:
            bool: `True` when both hold the same events.

        """

        return isinstance(other, Events) and self.events == other.events

    def __hash__(self) -> int:
        """
        Hash the members.

        Returns:
            int: A hash consistent with `__eq__`.

        """

        return hash(self.events)

    def __iter__(self) -> Iterator[Event | UpdateOf]:
        """
        Walk the members.

        Returns:
            Iterator[Event | UpdateOf]: The events, in order.

        """

        return iter(self.events)

    def __or__(self, other: EventClause) -> Events:
        """
        Combine this list with another event or list.

        Returns:
            Events: The combined event list.

        """

        return Events(self, other)

    def __repr__(self) -> str:
        """
        Show the members as they would be written.

        Returns:
            str: A reconstructable representation.

        """

        return " | ".join(repr(event) for event in self.events)

    @property
    def base_events(self) -> frozenset[Event]:
        """
        Report the plain events this clause covers.

        Returns:
            frozenset[Event]: Union of every member's base events.

        """

        return frozenset().union(*(event.base_events for event in self.events))

    @override
    def render(self, table: Table) -> str:
        """
        Render the event list.

        Returns:
            str: Events joined with `OR`.

        """

        return f" {LogicalOperator.OR} ".join(
            event.render(table) for event in self.events
        )


########################################################################################


@final
class UpdateOf(Clause, Renderable):
    """
    `UPDATE OF col, ...`: fire only when one of the listed columns is assigned.

    Accepts ORM attribute names or raw column names;
    both resolve against the table at compile time.

    PostgreSQL tests whether a column was *mentioned* by the `UPDATE`, not whether
    its value actually changed. Use an `AnyChange` condition for the latter.
    """

    __slots__ = ("columns",)

    def __init__(self, *columns: str) -> None:
        """
        Store the column names.

        Raises:
            ValueError: No columns were given.

        """

        if not columns:
            raise ValueError("Must provide at least one column.")

        self.columns: Sequence[str] = columns

    def __eq__(self, other: object) -> bool:
        """
        Compare two clauses by their column names.

        Returns:
            bool: `True` when both name the same columns.

        """

        return isinstance(other, UpdateOf) and self.columns == other.columns

    def __hash__(self) -> int:
        """
        Hash the column names.

        Returns:
            int: A hash consistent with `__eq__`.

        """

        return hash(self.columns)

    def __or__(self, other: EventClause) -> Events:
        """
        Combine this clause with another event.

        Returns:
            Events: The combined event list.

        """

        return Events(self, other)

    def __repr__(self) -> str:
        """
        Show the column names.

        Returns:
            str: A reconstructable representation.

        """

        rendered = ", ".join(repr(column) for column in self.columns)

        return f"UpdateOf({rendered})"

    @property
    def base_events(self) -> frozenset[Event]:
        """
        Report the plain events this clause covers.

        Returns:
            frozenset[Event]: Always `UPDATE`.

        """

        return frozenset({Event.UPDATE})

    @override
    def render(self, table: Table) -> str:
        """
        Render the event, resolving column names against the table.

        Returns:
            str: The `UPDATE OF` clause.

        """

        resolved = resolve_columns(self.columns, table)
        rendered = ", ".join(quote_column(column) for column in resolved)

        return f"UPDATE OF {rendered}"


########################################################################################


@final
class Referencing(Clause):
    """
    The `REFERENCING` clause of a statement-level trigger.

    Names the transition tables holding every row the statement touched.
    At least one of `old` and `new` is required, and PostgreSQL only allows
    transition tables for a single event, so a trigger declared on
    `INSERT | UPDATE` cannot have one.
    """

    __slots__ = ("new", "old")

    def __init__(self, *, new: str | None = None, old: str | None = None) -> None:
        """
        Store the transition table names.

        Raises:
            ValueError: Neither side was named.

        """

        if not new and not old:
            raise ValueError('Must provide at least one of "new" or "old".')

        self.new = new
        self.old = old

    def __eq__(self, other: object) -> bool:
        """
        Compare two clauses by their transition table names.

        Returns:
            bool: `True` when both name the same tables.

        """

        return (
            isinstance(other, Referencing)
            and self.new == other.new
            and self.old == other.old
        )

    def __hash__(self) -> int:
        """
        Hash the transition table names.

        Returns:
            int: A hash consistent with `__eq__`.

        """

        return hash((self.old, self.new))

    def __repr__(self) -> str:
        """
        Show the transition table names.

        Returns:
            str: A reconstructable representation.

        """

        return f"Referencing(new={self.new!r}, old={self.old!r})"

    @override
    def render(self, table: Table) -> str:
        """
        Render the clause.

        Returns:
            str: The `REFERENCING` clause.

        """

        parts = ["REFERENCING"]

        if self.old:
            parts.append(f"OLD TABLE AS {self.old}")
        if self.new:
            parts.append(f"NEW TABLE AS {self.new}")

        return " ".join(parts)
