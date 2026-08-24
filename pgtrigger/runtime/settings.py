"""
Reading and writing the run-time parameters triggers consult.
"""

from typing import TYPE_CHECKING

from sqlalchemy.engine import Engine

import pgtrigger.registry

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pgtrigger.aliases import Connectable, Executor
    from pgtrigger.registry import RegistryEntry

########################################################################################


def require_scoped(connectable: Connectable, what: str) -> Executor:
    """
    Reject connectables that would not share a connection with your queries.

    Returns:
        Executor: The connectable, unchanged.

    Raises:
        TypeError: An `Engine`, or something that cannot run SQL.

    """

    if isinstance(connectable, Engine):
        raise TypeError(
            f"{what}() needs a Connection or Session, not an Engine. An Engine"
            " hands out a different connection per statement, so the setting"
            " would not apply to your queries."
        )

    if not hasattr(connectable, "execute"):
        raise TypeError(
            f"{what}() expected a Connection or Session; got"
            f" {type(connectable).__name__}."
        )

    return connectable


########################################################################################


def deferrable(*uris: str) -> list[RegistryEntry]:
    """
    Resolve URIs to registrations, keeping only deferrable triggers.

    With no URIs given, non-deferrable triggers are skipped, since "all of them"
    plainly means "all the ones this applies to". Name one explicitly and it is
    an error, because you asked for something that cannot happen.

    Returns:
        list[Registration]: The matching registrations.

    Raises:
        ValueError: A named trigger is not deferrable.

    """

    registrations = pgtrigger.registry.registered(*uris)

    if not uris:
        return [
            r
            for r in registrations
            if r.trigger.execution is not None and r.trigger.execution.deferrable
        ]

    for registration in registrations:
        execution = registration.trigger.execution

        if execution is None or not execution.deferrable:
            raise ValueError(
                f'Trigger "{registration.uri}" is not deferrable. Declare it'
                " with execution=Execution.DEFERRED or Execution.IMMEDIATE."
            )

    return registrations


########################################################################################


def parse_array(value: str | None) -> list[str]:
    """
    Read a Postgres array literal back into a list.

    Returns:
        list[str]: The elements, or empty.

    """

    if not value:
        return []

    trimmed = value.strip().removeprefix("{").removesuffix("}")

    return [item for item in (part.strip() for part in trimmed.split(",")) if item]


def render_array(values: Sequence[str]) -> str:
    """
    Render a Postgres array literal.

    No quoting is needed: the only things written here are generated trigger
    identifiers, which are lower-case letters, digits, and underscores.

    Returns:
        str: An array literal.

    """

    return "{" + ",".join(sorted(set(values))) + "}"


########################################################################################


def pgids(*uris: str) -> list[str]:
    """
    Resolve URIs to the identifiers their triggers carry in Postgres.

    Returns:
        list[str]: The identifiers.

    """

    return [registration.pgid for registration in pgtrigger.registry.registered(*uris)]
