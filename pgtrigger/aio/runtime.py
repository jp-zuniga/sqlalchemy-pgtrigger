"""
Async `pgtrigger.runtime` state.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text

import pgtrigger.registry
import pgtrigger.runtime

from pgtrigger.config import CONFIG
from pgtrigger.consts import READ_SETTING, WRITE_SETTING
from pgtrigger.core import Execution

from .bind import require_scoped

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pgtrigger.aliases import Connectable

########################################################################################


@asynccontextmanager
async def ignore(connectable: Connectable, *uris: str) -> AsyncGenerator[None]:
    """
    Stand triggers down for the duration of the block.

    Behaves exactly as `pgtrigger.ignore` does.

    ```python
    async with pgtrigger.aio.ignore(session, "orders:no_deletes"):
        await session.delete(order)
    ```

    Yields:
        AsyncGenerator: An async context manager.

    """

    executor = require_scoped(connectable, "ignore")

    name = CONFIG.ignore_setting

    result = await executor.execute(READ_SETTING, {"name": name})
    previous = result.scalar()

    combined = pgtrigger.runtime.render_array([
        *pgtrigger.runtime.parse_array(previous),
        *pgtrigger.runtime.pgids(*uris),
    ])

    await executor.execute(WRITE_SETTING, {"name": name, "value": combined})

    try:
        yield
    finally:
        restored = pgtrigger.runtime.render_array(
            pgtrigger.runtime.parse_array(previous)
        )

        await executor.execute(WRITE_SETTING, {"name": name, "value": restored})


async def ignored(connectable: Connectable) -> list[str]:
    """
    List the trigger identifiers currently being ignored on a connection.

    Returns:
        list[str]: The Postgres identifiers.

    """

    executor = require_scoped(connectable, "ignored")

    result = await executor.execute(READ_SETTING, {"name": CONFIG.ignore_setting})

    return pgtrigger.runtime.parse_array(result.scalar())


async def is_ignored(connectable: Connectable, uri: str) -> bool:
    """
    Report whether a trigger is currently standing down on a connection.

    Returns:
        bool: `True` if the trigger will not fire.

    """

    registration = pgtrigger.registry.registered(uri)[0]

    return registration.pgid in await ignored(connectable)


########################################################################################


async def constraints(
    connectable: Connectable,
    execution: Execution,
    *uris: str,
) -> None:
    """
    Retime deferrable triggers for the rest of the transaction.

    Behaves exactly as `pgtrigger.constraints` does.

    Raises:
        ValueError: A named trigger is not deferrable, or `execution` is not a
                    timing.

    """

    if not isinstance(execution, Execution) or not execution.deferrable:
        raise ValueError(
            f'Invalid "execution": {execution!r}. Expected Execution.DEFERRED or'
            " Execution.IMMEDIATE."
        )

    executor = require_scoped(connectable, "constraints")

    registrations = pgtrigger.runtime.deferrable(*uris)

    if not registrations:
        return

    names = ", ".join(registration.pgid for registration in registrations)

    await executor.execute(text(f"SET CONSTRAINTS {names} {execution}"))
