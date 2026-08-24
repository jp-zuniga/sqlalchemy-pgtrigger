"""
Retiming deferrable triggers.
"""

from typing import TYPE_CHECKING

from sqlalchemy import text

from pgtrigger.core import Execution

from .settings import deferrable, require_scoped

if TYPE_CHECKING:
    from pgtrigger.aliases import Connectable


########################################################################################


def constraints(connectable: Connectable, execution: Execution, *uris: str) -> None:
    """
    Retime deferrable triggers for the rest of the transaction.

    Set them `DEFERRED` and they hold off until commit, so intermediate states
    that would fail the check are allowed as long as the state at commit is
    sound.

    Args:
        connectable: A `Session` or `Connection` inside a transaction.
        execution: `Execution.DEFERRED` or `Execution.IMMEDIATE`.
        *uris: Triggers to retime. With none given, every deferrable trigger.

    ```python
    with session.begin():
        pgtrigger.constraints(session, pgtrigger.Execution.DEFERRED)
        ...
    ```

    Raises:
        ValueError: A named trigger is not deferrable, or `execution` is not a timing.
        RuntimeError: The connection is not in a transaction,
                      where `SET CONSTRAINTS` would have no effect.

    """

    if not isinstance(execution, Execution) or not execution.deferrable:
        raise ValueError(
            f'Invalid "execution": {execution!r}. '
            "Expected Execution.DEFERRED or Execution.IMMEDIATE."
        )

    executor = require_scoped(connectable, "constraints")
    registrations = deferrable(*uris)

    if not registrations:
        return

    in_transaction = getattr(executor, "in_transaction", None)

    if in_transaction is not None and not in_transaction():
        raise RuntimeError(
            "constraints() has to run inside a transaction; "
            "SET CONSTRAINTS has no effect outside one."
        )

    # identifiers are generated and match [a-z0-9_]+, so there is nothing here
    # to inject, and SET CONSTRAINTS does not accept bind parameters
    names = ", ".join(registration.pgid for registration in registrations)

    executor.execute(text(f"SET CONSTRAINTS {names} {execution}"))
