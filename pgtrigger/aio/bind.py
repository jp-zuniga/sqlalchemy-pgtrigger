"""
Bridging between an async connectable and the synchronous API.
"""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import Connection

    from pgtrigger.aliases import AsyncConnectable, AsyncExecutor, Connectable

########################################################################################


def require_scoped(connectable: Connectable, what: str) -> AsyncExecutor:
    """
    Reject connectables that would not share a connection with your queries.

    Returns:
        AsyncExecutor: The connectable, unchanged.

    Raises:
        TypeError: An `AsyncEngine`, or something that cannot run SQL.

    """

    if isinstance(connectable, AsyncEngine):
        raise TypeError(
            f"aio.{what}() needs an AsyncConnection or AsyncSession, not an"
            " AsyncEngine. An engine hands out a different connection per"
            " statement, so the setting would not apply to your queries."
        )

    if not isinstance(connectable, AsyncConnection | AsyncSession):
        raise TypeError(
            f"aio.{what}() expected an AsyncConnection or AsyncSession; got"
            f" {type(connectable).__name__}."
        )

    return connectable


async def run_sync[T](
    connectable: AsyncConnectable,
    fn: Callable[[Connection], T],
) -> T:
    """
    Run a synchronous-API callable against an async connectable.

    Returns:
        T: Whatever the callable returned.

    Raises:
        TypeError: The argument is not an async connectable.

    """

    if isinstance(connectable, AsyncEngine):
        async with connectable.begin() as connection:
            return await connection.run_sync(fn)

    if isinstance(connectable, AsyncConnection | AsyncSession):
        return await connectable.run_sync(fn)  # ty: ignore[invalid-argument-type]

    raise TypeError(
        "Expected an AsyncEngine, AsyncConnection, or AsyncSession; got"
        f" {type(connectable).__name__}."
    )
