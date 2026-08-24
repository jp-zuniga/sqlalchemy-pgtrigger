"""
The declarative half of the package.

A `Trigger` and the clauses it is built from are ordinary Python objects that
know how to render themselves against a table. Nothing here talks to a
database; that is `installation` and `migrations`.
"""

from typing import TYPE_CHECKING

from .clauses import Event, Events, Execution, ForEach, Referencing, Time, UpdateOf
from .conditions import SQL, Composite, Condition, Not, Q
from .func import Func
from .providers import Clause, Renderable, Statement
from .proxy import RowProxy, RowScope, new, old

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "SQL",
    "Clause",
    "Composite",
    "Condition",
    "Event",
    "Events",
    "Execution",
    "ForEach",
    "Func",
    "Not",
    "Q",
    "Referencing",
    "Renderable",
    "RowProxy",
    "RowScope",
    "Statement",
    "Time",
    "UpdateOf",
    "new",
    "old",
)
