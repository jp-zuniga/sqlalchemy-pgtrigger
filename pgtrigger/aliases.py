"""
Type aliases for the things callers hand this package.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import SimpleNamespace

    from sqlalchemy import ColumnElement, Table

    from pgtrigger.core import Event, Events, ForEach, Func, RowProxy, UpdateOf


########################################################################################

type EventClause = Event | Events | UpdateOf
"""
Anything usable as the event list of a trigger.
"""

type FuncSource = str | Func | Mapping[ForEach, str | Func]
"""
A function body, or one per level for a trigger that serves both.
"""

type FuncContext = SimpleNamespace | Table | str
"""
A value a `Func` template can interpolate.
"""

type Predicate = Callable[[RowProxy, RowProxy], ColumnElement]
"""
A callable taking `(old, new)` row proxies and returning a boolean expression.
"""
