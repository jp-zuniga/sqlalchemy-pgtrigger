"""
Conditions that compare a row before and after.
"""

from copy import deepcopy
from typing import TYPE_CHECKING, override

from sqlalchemy import and_, or_

from pgtrigger.core import Condition
from pgtrigger.enums import LogicalOperator
from pgtrigger.utils import compile_expression, resolve_columns

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy import ColumnElement

    from pgtrigger.core import RowScope

########################################################################################


class Change(Condition):
    """
    Base for the change-detection conditions. See the subclasses.
    """

    __slots__ = (
        "all_fields",
        "comparison",
        "exclude",
        "exclude_auto",
        "fields",
        "negated",
    )

    def __init__(
        self,
        *fields: str,
        exclude: Iterable[str] | None = None,
        exclude_auto: bool = False,
        all_fields: bool = False,
        comparison: LogicalOperator = LogicalOperator.IS_DISTINCT,
    ) -> None:
        """
        Store the fields to watch and how to compare them.
        """

        self.fields: list[str] = list(fields)
        self.exclude: list[str] = list(exclude or [])
        self.exclude_auto = exclude_auto
        self.all_fields = all_fields
        self.comparison = comparison
        self.negated = False

    @override
    def __invert__(self) -> Change:
        """
        Negate the comparison.

        Returns:
            Change: A copy that renders wrapped in `NOT`.

        """

        inverted = deepcopy(self)
        inverted.negated = not inverted.negated

        return inverted

    @override
    def resolve(self, scope: RowScope) -> str:
        """
        Render the comparison over the selected columns.

        Returns:
            str: The condition SQL.

        Raises:
            ValueError: Every column was excluded.

        """

        table = scope.table

        exclude_keys = {c.key for c in resolve_columns(self.exclude, table)}

        if self.exclude_auto:
            for column in table.columns:
                if column.onupdate is not None or column.server_onupdate is not None:
                    exclude_keys.add(column.key)

        all_keys = {c.key for c in table.columns}

        selected = (
            {c.key for c in resolve_columns(self.fields, table)}
            if self.fields
            else set(all_keys)
        )

        keys = sorted(key for key in selected if key not in exclude_keys)

        if not keys:
            raise ValueError(
                f"No fields remain for {type(self).__name__} on table"
                f' "{table.name}" after exclusions.'
            )

        if set(keys) == all_keys and not self.all_fields:
            # whole-row comparison is both cheaper and shorter
            expression = f"{scope.old_alias}.* {self.comparison} {scope.new_alias}.*"
        else:
            expression = compile_expression(self._clauses(scope, keys))

        return f"{LogicalOperator.NOT} ({expression})" if self.negated else expression

    def _clauses(self, scope: RowScope, keys: list[str]) -> ColumnElement:
        """
        Build one comparison per column and join them.

        Returns:
            ColumnElement: The combined expression.

        """

        new, old = scope.new, scope.old

        clauses = [
            old[key].is_distinct_from(new[key])
            if self.comparison is LogicalOperator.IS_DISTINCT
            else old[key].is_not_distinct_from(new[key])
            for key in keys
        ]

        return and_(*clauses) if self.all_fields else or_(*clauses)


########################################################################################


class AnyChange(Change):
    """
    Fire when *any* of the supplied fields change.
    """

    __slots__ = ()

    @override
    def __init__(
        self,
        *fields: str,
        exclude: Iterable[str] | None = None,
        exclude_auto: bool = False,
    ) -> None:
        """
        Watch the given fields, defaulting to every column on the table.

        Args:
            *fields: Fields to watch. Defaults to every column on the table.
            exclude: Fields to leave out.
            exclude_auto: Leave out columns carrying an `onupdate` or
                          `server_onupdate`.

        """

        super().__init__(
            *fields,
            exclude=exclude,
            exclude_auto=exclude_auto,
            all_fields=False,
        )


class AnyDontChange(Change):
    """
    Fire when *any* of the supplied fields do not change.
    """

    __slots__ = ()

    @override
    def __init__(
        self,
        *fields: str,
        exclude: Iterable[str] | None = None,
        exclude_auto: bool = False,
    ) -> None:
        """
        Watch the given fields, defaulting to every column on the table.

        Args:
            *fields: Fields to watch. Defaults to every column on the table.
            exclude: Fields to leave out.
            exclude_auto: Leave out columns carrying an `onupdate` or
                          `server_onupdate`.

        """

        super().__init__(
            *fields,
            exclude=exclude,
            exclude_auto=exclude_auto,
            all_fields=False,
            comparison=LogicalOperator.NOT_DISTINCT,
        )


class AllChange(Change):
    """
    Fire when *all* of the supplied fields change.
    """

    __slots__ = ()

    @override
    def __init__(
        self,
        *fields: str,
        exclude: Iterable[str] | None = None,
        exclude_auto: bool = False,
    ) -> None:
        """
        Watch the given fields, defaulting to every column on the table.

        Args:
            *fields: Fields to watch. Defaults to every column on the table.
            exclude: Fields to leave out.
            exclude_auto: Leave out columns carrying an `onupdate` or `server_onupdate`.

        """

        super().__init__(
            *fields,
            exclude=exclude,
            exclude_auto=exclude_auto,
            all_fields=True,
        )


class AllDontChange(Change):
    """
    Fire when *all* of the supplied fields do not change.
    """

    __slots__ = ()

    @override
    def __init__(
        self,
        *fields: str,
        exclude: Iterable[str] | None = None,
        exclude_auto: bool = False,
    ) -> None:
        """
        Watch the given fields, defaulting to every column on the table.

        Args:
            *fields: Fields to watch. Defaults to every column on the table.
            exclude: Fields to leave out.
            exclude_auto: Leave out columns carrying an `onupdate` or `server_onupdate`.

        """

        super().__init__(
            *fields,
            exclude=exclude,
            exclude_auto=exclude_auto,
            all_fields=True,
            comparison=LogicalOperator.NOT_DISTINCT,
        )
