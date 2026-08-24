"""
The trigger registry.

Every declared trigger lands here, keyed by a URI of the form `<schema>.table:name`:
`orders:no_deletes`, `billing.invoices:read_only`.

This is the single record of what has been declared. Installation, runtime, and
`autogenerate` all read from it, so a trigger that is not registered does not
exist as far as this package is concerned.
"""

from typing import TYPE_CHECKING

from .decorator import register, resolve_table
from .entry import RegistryEntry
from .store import (
    add,
    clear,
    for_metadata,
    for_table,
    iterate,
    registered,
    remove,
    uris,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "RegistryEntry",
    "add",
    "clear",
    "for_metadata",
    "for_table",
    "iterate",
    "register",
    "registered",
    "remove",
    "resolve_table",
    "uris",
)
