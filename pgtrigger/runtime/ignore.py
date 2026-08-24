"""
Standing triggers down for a block of code.
"""

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pgtrigger.registry

from pgtrigger.config import CONFIG
from pgtrigger.consts import READ_SETTING, WRITE_SETTING

from .settings import parse_array, pgids, render_array, require_scoped

if TYPE_CHECKING:
    from collections.abc import Generator

    from pgtrigger.aliases import Connectable


########################################################################################


@contextmanager
def ignore(connectable: Connectable, *uris: str) -> Generator[None]:
    """
    Stand triggers down for the duration of the block.

    Nested calls compose:
    the inner block adds to the ignore set and puts back what it found on the way out.

    Args:
        connectable: The `Session` or `Connection` that will run the statements.
        *uris: Triggers to ignore.
               A `table:*` pattern takes a whole table.
               Defaults to all.

    ```python
    with pgtrigger.ignore(session, "orders:no_deletes"):
        session.delete(order)
    ```

    Only triggers this package created can be ignored;
    the check lives in the generated function body.

    Yields:
        Generator: A context manager.

    """

    executor = require_scoped(connectable, "ignore")

    name = CONFIG.ignore_setting

    previous = executor.execute(READ_SETTING, {"name": name}).scalar()

    combined = render_array([*parse_array(previous), *pgids(*uris)])

    executor.execute(WRITE_SETTING, {"name": name, "value": combined})

    try:
        yield
    finally:
        restored = render_array(parse_array(previous))

        executor.execute(WRITE_SETTING, {"name": name, "value": restored})


def ignored(connectable: Connectable) -> list[str]:
    """
    List the trigger identifiers currently being ignored on a connection.

    Returns:
        list[str]: The Postgres identifiers.

    """

    executor = require_scoped(connectable, "ignored")

    value = executor.execute(READ_SETTING, {"name": CONFIG.ignore_setting}).scalar()

    return parse_array(value)


def is_ignored(connectable: Connectable, uri: str) -> bool:
    """
    Report whether a trigger is currently standing down on a connection.

    ```python
    with pgtrigger.ignore(session, "orders:no_deletes"):
        pgtrigger.is_ignored(session, "orders:no_deletes")  # True
    ```

    Returns:
        bool: `True` if the trigger will not fire.

    """

    registration = pgtrigger.registry.registered(uri)[0]

    return registration.pgid in ignored(connectable)
