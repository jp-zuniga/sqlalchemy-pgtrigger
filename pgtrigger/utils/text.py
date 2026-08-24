"""
Naming and fingerprinting.
"""

from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy import Table

########################################################################################


def hex_digest(*, length: int | None = None, value: str) -> str:
    """
    Fingerprint a string.

    Used to spot drift between a declaration and what is installed, and to give
    each trigger a table-specific suffix. Not a security boundary.

    Defaults to the whole digest. Truncation is for the identifier suffix, where
    63 characters have to cover the prefix and the trigger name as well; a
    shortened fingerprint would let a changed trigger read as unchanged.

    Returns:
        str: A hex digest, truncated to `length` when one is given.

    """

    hexdigest = sha256(value.encode()).hexdigest()

    return hexdigest[:length] if length else hexdigest


########################################################################################


def table_uri(table: Table) -> str:
    """
    Build the registry key prefix for a table: `<schema>.table`.

    Unquoted, because this identifies a trigger to a human and to the registry,
    not to PostgreSQL.

    Returns:
        str: The table portion of a trigger URI.

    """

    return f"{table.schema}.{table.name}" if table.schema else table.name
