"""
Marking a row instead of removing it.
"""

from typing import TYPE_CHECKING, final, override

from pgtrigger.core import Event, Time, Trigger
from pgtrigger.utils import (
    dedent_sql,
    pk_columns,
    quote_column,
    quote_literal,
    quote_table,
    resolve_column,
)

from typing_extensions import Sentinel

if TYPE_CHECKING:
    from typing import Unpack

    from sqlalchemy import Table

    from pgtrigger.aliases import SoftDeleteValue
    from pgtrigger.core import TriggerKwargs


########################################################################################


@final
class SoftDelete(Trigger):
    """
    Marks a row instead of removing it.

    ```python
    pgtrigger.SoftDelete(field="is_active", name="soft_delete")
    ```

    The `DELETE` still appears to succeed, so an ORM that issues one,
    or a repository doing a bulk delete, sees nothing unusual while the row stays put.
    Reads have to filter the marker column themselves;
    this only stops the row from going away.

    Because the trigger runs `BEFORE DELETE` and returns `NULL`,
    the original delete is cancelled and replaced by an update.
    That means `ON DELETE CASCADE` on other tables does not fire,
    which is usually what you want and occasionally a surprise.

    Supports nullable boolean, string, and integer columns, and composite primary keys.
    """

    field: str
    """
    Column marking the row as deleted. Required.
    """

    value: SoftDeleteValue
    """
    What to set it to.
    """

    def __init__(
        self,
        *,
        field: str | None = None,
        value: Sentinel | SoftDeleteValue = False,
        **kwargs: Unpack[TriggerKwargs],
    ) -> None:
        """
        Take the marker column and its value, then hand the rest on.

        `value` uses a sentinel rather than `None` as its default, because
        `None` is itself a usable marker.

        Raises:
            ValueError: No `field` was given.

        """

        if field is not None:
            self.field = field

        if not isinstance(value, Sentinel):
            self.value = value

        if not self.field:
            raise ValueError('Must provide "field" to SoftDelete.')

        kwargs.setdefault("events", Event.DELETE)
        kwargs.setdefault("time", Time.BEFORE)

        super().__init__(**kwargs)

    @override
    def get_func(self, table: Table) -> str:
        """
        Update the marker column, then cancel the delete.

        Returns:
            str: The function body.

        """

        marker = quote_column(resolve_column(self.field or "", table))
        keys = pk_columns(table)

        columns = ", ".join(quote_column(key) for key in keys)
        values = ", ".join(f"OLD.{quote_column(key)}" for key in keys)

        if len(keys) > 1:
            columns = f"({columns})"
            values = f"({values})"

        return dedent_sql(f"""
            UPDATE {quote_table(table)}
            SET {marker} = {self._rendered_value}
            WHERE {columns} = {values};
            RETURN NULL;
        """)  # ruff: ignore[hardcoded-sql-expression]

    @property
    def _rendered_value(self) -> str:
        """
        Render the marker value as a SQL literal.

        Returns:
            str: A literal safe to inline.

        """

        match self.value:
            case None:
                return "NULL"
            case bool():
                return str(self.value).upper()
            case str():
                return quote_literal(self.value)
            case _:
                return str(self.value)
