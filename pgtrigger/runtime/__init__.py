"""
Standing triggers down for a block of code, and retiming deferred ones.

A trigger consults a Postgres run-time parameter before it does anything,
and `ignore` writes the trigger's identifier into it. The write is transaction-local
with `set_config(..., is_local => true)`, so it is discarded on commit or rollsback
whatever happens in between.

You name the `Session` or `Connection` that will run the statements.
An `Engine` is refused, because it hands out a different connection per
statement and the setting would not follow your queries.

This is not the same thing as `disable`, which is an `ALTER TABLE` that stops
the trigger firing for everyone until it is enabled again.
"""

from typing import TYPE_CHECKING

from .constraints import constraints
from .ignore import ignore, ignored, is_ignored
from .settings import deferrable, parse_array, pgids, render_array, require_scoped

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "constraints",
    "deferrable",
    "ignore",
    "ignored",
    "is_ignored",
    "parse_array",
    "pgids",
    "render_array",
    "require_scoped",
)
