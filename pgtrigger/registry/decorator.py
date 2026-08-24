"""
Attaching triggers to something other than `__table_args__`.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Table, inspect
from sqlalchemy.orm import Mapper

if TYPE_CHECKING:
    from collections.abc import Callable

    from pgtrigger.core import Trigger

########################################################################################


def register[T](*triggers: Trigger) -> Callable[[T], T]:
    """
    Attach triggers to a declarative class or a Core `Table`.

    Declaring them in `__table_args__` is usually clearer. This is for models
    you do not own, and for cases where the triggers are assembled elsewhere.

    ```python
    @pgtrigger.register(
        pgtrigger.Protect(
            name="append_only",
            events=(pgtrigger.Event.UPDATE | pgtrigger.Event.DELETE),
        )
    )
    class Order(Base):
        __tablename__ = "orders"
    ```

    Returns:
        Callable[[T], T]: A decorator returning its argument unchanged.

    """

    def wrapper(target: T) -> T:
        table = resolve_table(target)

        for trigger in triggers:
            trigger.attach(table)

        return target

    return wrapper


########################################################################################


def resolve_table(target: object) -> Table:
    """
    Coerce a declarative class, mapper, or `Table` into a `Table`.

    Returns:
        Table: The underlying table.

    Raises:
        TypeError: Nothing table-like could be found.

    """

    if isinstance(target, Table):
        return target

    attribute = getattr(target, "__table__", None)

    if isinstance(attribute, Table):
        return attribute

    mapper = inspect(target, raiseerr=False)

    if isinstance(mapper, Mapper) and isinstance(mapper.local_table, Table):
        return mapper.local_table

    raise TypeError(
        f"Cannot resolve a Table from {target!r}. Pass a declarative class, a"
        " mapper, or a sqlalchemy.Table."
    )
