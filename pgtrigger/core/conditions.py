"""
The `WHEN` clause of a trigger, and the ways of building one.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, final, override

from sqlalchemy import ColumnElement

from pgtrigger.enums import LogicalOperator
from pgtrigger.utils import compile_expression

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from pgtrigger.aliases import Predicate

    from .proxy import RowScope

########################################################################################


class Condition(ABC):
    """
    Base for the `WHEN` clause of a trigger.

    Conditions resolve lazily against a scope, because `__table_args__` is
    evaluated before the table exists. Combine them with `&`, `|`, and `~`.
    """

    __slots__ = ()

    @abstractmethod
    def resolve(self, scope: RowScope) -> str:
        """
        Render this condition against a scope.

        Returns:
            str: SQL, without the surrounding `WHEN (...)`.

        """

    @final
    def __and__(self, other: Condition) -> Condition:
        """
        Combine two conditions with `AND`.

        Returns:
            Condition: The combined condition.

        """

        return Composite(LogicalOperator.AND, self, other)

    def __invert__(self) -> Condition:
        """
        Negate this condition.

        Returns:
            Condition: The negated condition.

        """

        return Not(self)

    @final
    def __or__(self, other: Condition) -> Condition:
        """
        Combine two conditions with `OR`.

        Returns:
            Condition: The combined condition.

        """

        return Composite(LogicalOperator.OR, self, other)


########################################################################################


@final
class Composite(Condition):
    """
    Two or more conditions joined by `AND` or `OR`.

    Built by the `&` and `|` operators rather than directly.
    """

    __slots__ = ("conditions", "operator")

    def __init__(
        self,
        operator: Literal[LogicalOperator.AND, LogicalOperator.OR],
        *conditions: Condition,
    ) -> None:
        """
        Store the operator and the conditions it joins.
        """

        self.operator = operator
        self.conditions: Sequence[Condition] = conditions

    def __repr__(self) -> str:
        """
        Show the joined conditions.

        Returns:
            str: A parenthesised representation.

        """

        joined = f" {self.operator} ".join(repr(c) for c in self.conditions)

        return f"({joined})"

    @override
    def resolve(self, scope: RowScope) -> str:
        """
        Render each side, parenthesised so precedence cannot surprise.

        Returns:
            str: The combined SQL.

        """

        return f" {self.operator} ".join(
            f"({condition.resolve(scope)})" for condition in self.conditions
        )


########################################################################################


@final
class Not(Condition):
    """
    The negation of a condition.

    Built by the `~` operator rather than directly.
    """

    __slots__ = ("condition",)

    def __init__(self, condition: Condition) -> None:
        """
        Store the condition being negated.
        """

        self.condition = condition

    def __repr__(self) -> str:
        """
        Show the negated condition.

        Returns:
            str: A short representation.

        """

        return f"~{self.condition!r}"

    @override
    def resolve(self, scope: RowScope) -> str:
        """
        Render the negation.

        Returns:
            str: The negated SQL.

        """

        return f"{LogicalOperator.NOT} ({self.condition.resolve(scope)})"


########################################################################################


@final
class SQL(Condition):
    """
    A condition written out by hand.

    An escape hatch for anything the expression language cannot reach.
    Nothing is validated or quoted, so the SQL has to be correct already:

    ```python
    pgtrigger.SQL('OLD."status" IS DISTINCT FROM NEW."status"')
    ```
    """

    __slots__ = ("sql",)

    def __init__(self, sql: str) -> None:
        """
        Store the SQL.

        Raises:
            ValueError: The SQL is empty.

        """

        if not sql or not sql.strip():
            raise ValueError("Must provide SQL to a condition.")

        self.sql = sql

    def __repr__(self) -> str:
        """
        Show the SQL.

        Returns:
            str: A reconstructable representation.

        """

        return f"SQL({self.sql!r})"

    @override
    def resolve(self, scope: RowScope) -> str:
        """
        Return the SQL unchanged.

        Returns:
            str: The SQL as given.

        """

        return self.sql


########################################################################################


@final
class Q(Condition):
    """
    A condition built from the SQLAlchemy expression language.

    Pass a callable taking `(old, new)` row proxies.
    It runs at compile time, once the table is known,
    and its result is rendered with literals inlined.

    ```python
    pgtrigger.Q(lambda old, new: old.status != new.status)
    pgtrigger.Q(lambda old, new: new.total > 100)
    pgtrigger.Q(lambda old, new: sa.and_(new.seats < old.seats, old.plan == "pro"))
    ```

    An already-built expression is also accepted,
    for when the table is in scope at declaration time:

    ```python
    pgtrigger.Q(pgtrigger.old(Order.__table__).status != "draft")
    ```

    A bare callable passed to a trigger's `condition=` is wrapped in `Q` automatically,
    so this is rarely written out except to combine conditions.
    """

    __slots__ = ("expression",)

    def __init__(self, expression: ColumnElement | Predicate) -> None:
        """
        Store the expression or the callable that will build one.
        """

        self.expression = expression

    def __repr__(self) -> str:
        """
        Show the expression.

        Returns:
            str: A reconstructable representation.

        """

        return f"Q({self.expression!r})"

    @override
    def resolve(self, scope: RowScope) -> str:
        """
        Call the predicate, if given one, and render the expression.

        Returns:
            str: The rendered expression.

        Raises:
            TypeError: The predicate returned something that is not a
                       SQLAlchemy expression.

        """

        expression = self.expression

        if not isinstance(expression, ColumnElement) and callable(expression):
            expression = expression(scope.old, scope.new)

        if not isinstance(expression, ColumnElement):
            raise TypeError(
                "A pgtrigger.Q must resolve to a SQLAlchemy expression, got"
                f" {type(expression).__name__}."
            )

        return compile_expression(expression)


########################################################################################


def coerce_condition(condition: Condition | Predicate | None) -> Condition | None:
    """
    Accept a bare `(old, new)` callable where a `Condition` is expected.

    Returns:
        Condition | None: The condition, wrapped in `Q` when it was a callable.

    Raises:
        TypeError: The value is neither a condition nor callable.

    """

    if condition is None or isinstance(condition, Condition):
        return condition

    if callable(condition):
        return Q(condition)

    raise TypeError(
        f'Invalid "condition": {condition!r}. Expected a Condition or a'
        " callable taking (old, new)."
    )
