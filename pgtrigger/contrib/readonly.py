"""
Refusing edits to columns.
"""

from typing import TYPE_CHECKING, override

from pgtrigger.core import Event

from .conditions import AnyChange
from .protect import Protect

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Unpack

    from sqlalchemy import Table

    from pgtrigger.core import Condition, TriggerKwargs

########################################################################################


class ReadOnly(Protect):
    """
    Refuses edits to columns.

    Pass `fields` to freeze only those,
    `exclude` to freeze everything else,
    or neither to make the whole row immutable.

    Names may be ORM attributes or database column names.

    ```python
    pgtrigger.ReadOnly(fields=("total",), name="frozen_total")
    pgtrigger.ReadOnly(exclude=("updated_at",), name="frozen")
    ```

    A `condition` is kept and combined with the change check,
    so immutability can be scoped to part of a row's life:

    ```python
    pgtrigger.ReadOnly(
        condition=(lambda old, new: old.status == "shipped"),
        fields=("address",),
        name="frozen_once_shipped",
    )
    ```

    Note the difference from `UpdateOf`, which fires when a column is *assigned*
    even if the value is unchanged. This fires only on a real change.
    """

    fields: Iterable[str] | None = None
    """
    Columns to freeze. Mutually exclusive with `exclude`.
    """

    exclude: Iterable[str] | None = None
    """
    Columns to leave writable; everything else is frozen.
    """

    @override
    def __init__(
        self,
        *,
        fields: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        **kwargs: Unpack[TriggerKwargs],
    ) -> None:
        """
        Take the columns to freeze, then hand the rest on to `Trigger`.

        Raises:
            ValueError: Both `fields` and `exclude` were given.

        """

        if fields is not None:
            self.fields = fields
        if exclude is not None:
            self.exclude = exclude

        if self.fields and self.exclude:
            raise ValueError('Pass only one of "fields" or "exclude" to ReadOnly.')

        kwargs.setdefault("events", Event.UPDATE)

        super().__init__(**kwargs)

    @override
    def get_condition(self, table: Table) -> Condition:
        """
        Fire when a frozen column actually changes.

        Returns:
            Condition: The change check, narrowed by any explicit condition.

        """

        change = AnyChange(*(self.fields or []), exclude=self.exclude)

        return change if self.condition is None else change & self.condition
