"""
Type aliases for the things callers hand this package.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import SimpleNamespace

    from sqlalchemy import ColumnElement, Connection, Engine, Table
    from sqlalchemy.orm import Session

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

type SoftDeleteValue = bool | int | str | None
"""
What a soft-deleted row's marker column is set to.
"""

########################################################################################

type Connectable = Connection | Engine | Session
"""
Anything that can run trigger DDL.

An `Engine` is given a transaction of its own;
a `Connection` or `Session` joins the one already open.
"""

type Executor = Connection | Session
"""
Something bound to a single connection.

Run-time state such as the ignore parameter is transaction-local, so it has to
be set on the connection that will run the statements. An `Engine` hands out a
different connection per statement and is refused.
"""
