"""
Reading and writing the registry.
"""

from typing import TYPE_CHECKING

from pgtrigger.consts import WILDCARD
from pgtrigger.utils import table_uri

from .entry import RegistryEntry

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import MetaData, Table

    from pgtrigger.core import Trigger

########################################################################################

TRIGGER_REGISTRY: dict[str, RegistryEntry] = {}

########################################################################################


def add(uri: str, *, table: Table, trigger: Trigger) -> None:
    """
    Record a trigger.

    Called by `Trigger.attach`; there is rarely a reason to call it directly.

    Raises:
        KeyError: The name, or the identifier derived from it, is already taken.

    """

    registration = RegistryEntry(table=table, trigger=trigger)

    existing = TRIGGER_REGISTRY.get(uri)

    if existing is not None:
        if existing.trigger is trigger:
            return

        raise KeyError(
            f'Trigger name "{trigger.name}" is already used on table'
            f' "{table_uri(table)}". Trigger names must be unique per table.'
        )

    pgid = registration.pgid

    collision = next((r for r in TRIGGER_REGISTRY.values() if r.pgid == pgid), None)

    if collision is not None:
        raise KeyError(
            f'Trigger "{uri}" produces the PostgreSQL identifier "{pgid}", which'
            f' "{collision.uri}" already uses. Rename one of them.'
        )

    TRIGGER_REGISTRY[uri] = registration


def clear() -> None:
    """
    Empty the registry.

    Chiefly for tests, which rebuild their metadata between modules.
    """

    TRIGGER_REGISTRY.clear()


def remove(uri: str) -> None:
    """
    Forget a trigger.

    Raises:
        KeyError: Nothing is registered under that URI.

    """

    if uri not in TRIGGER_REGISTRY:
        raise KeyError(f'URI "{uri}" is not in the pgtrigger registry.')

    del TRIGGER_REGISTRY[uri]


########################################################################################


def for_metadata(*metadata: MetaData) -> list[RegistryEntry]:
    """
    Collect every trigger declared on the tables of one or more `MetaData`.

    Autogenerate uses this to confine itself to the tables it was handed.

    Returns:
        list[Registration]: The matching registrations.

    """

    tables = {id(table) for md in metadata for table in md.tables.values()}

    return [r for r in TRIGGER_REGISTRY.values() if id(r.table) in tables]


def for_table(table: Table) -> list[RegistryEntry]:
    """
    Collect every trigger declared on a table.

    Matched on table identity rather than name, so two `MetaData` objects
    holding a table of the same name stay separate.

    Returns:
        list[Registration]: The matching registrations.

    """

    return [r for r in TRIGGER_REGISTRY.values() if r.table is table]


########################################################################################


def iterate() -> Iterator[RegistryEntry]:
    """
    Walk the registry without copying it.

    Returns:
        Iterator[Registration]: Every registration, in declaration order.

    """

    return iter(TRIGGER_REGISTRY.values())


########################################################################################


def registered(*uris: str) -> list[RegistryEntry]:
    """
    Look registrations up by URI.

    A `table:*` pattern selects every trigger on a table. With no URIs given,
    everything registered comes back.

    Returns:
        list[Registration]: The matching registrations.

    Raises:
        KeyError: A URI matches nothing.
        ValueError: A URI is malformed.

    """

    if not uris:
        return list(TRIGGER_REGISTRY.values())

    results: list[RegistryEntry] = []

    for uri in uris:
        if uri.count(":") != 1:
            raise ValueError(
                f'Malformed trigger URI "{uri}". Expected'
                ' "<schema>.table:trigger_name".'
            )

        if uri.endswith(WILDCARD):
            table = uri.removesuffix(WILDCARD)
            matched = [r for r in TRIGGER_REGISTRY.values() if r.table_uri == table]

            if not matched:
                raise KeyError(f'No triggers are registered on table "{table}".')

            results.extend(matched)
        elif (registration := TRIGGER_REGISTRY.get(uri)) is not None:
            results.append(registration)
        else:
            raise KeyError(f'URI "{uri}" is not in the pgtrigger registry.')

    return results


########################################################################################


def uris() -> list[str]:
    """
    List every registered URI.

    Returns:
        list[str]: The URIs, in declaration order.

    """

    return list(TRIGGER_REGISTRY)
