"""
PostgreSQL triggers for SQLAlchemy.

Triggers are declared where the rest of your schema is declared, in `__table_args__`,
and they are ordinary Python objects until the moment they become SQL:

```python
import pgtrigger


class Orders(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    status: Mapped[str]
    total: Mapped[int]

    __table_args__ = (
        pgtrigger.Protect(events=pgtrigger.Event.DELETE, name="no_deletes"),
        pgtrigger.ReadOnly(
            condition=(lambda old, new: old.status == "shipped"),
            fields=("total",),
            name="frozen_total",
        ),
    )
```

The vocabulary follows the PostgreSQL `CREATE TRIGGER` grammar,
so what you write and what PostgreSQL receives line up clause for clause.

Conditions are SQLAlchemy expressions over the `old` and `new` rows, which means
the expression language does the quoting, the type handling, and the literal
rendering rather than a bespoke filter syntax.
"""

from typing import TYPE_CHECKING

from pgtrigger.config import CONFIG, Config
from pgtrigger.contrib import (
    AllChange,
    AllDontChange,
    AnyChange,
    AnyDontChange,
    Protect,
    ReadOnly,
    SoftDelete,
)
from pgtrigger.core import (
    Composite,
    Event,
    Execution,
    ForEach,
    Func,
    Not,
    Referencing,
    Time,
    Trigger,
    UpdateOf,
    new,
    old,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "CONFIG",
    "AllChange",
    "AllDontChange",
    "AnyChange",
    "AnyDontChange",
    "Composite",
    "Config",
    "Event",
    "Execution",
    "ForEach",
    "Func",
    "Not",
    "Protect",
    "ReadOnly",
    "Referencing",
    "SoftDelete",
    "Time",
    "Trigger",
    "UpdateOf",
    "new",
    "old",
)

__author__: Final[str] = "Joaquín Zúñiga"
__copyright__: Final[str] = f"2026, {__author__}"
__email__: Final[str] = "jp.zuniga.dev@gmail.com"
__license__: Final[str] = "BSD-3-Clause"
__summary__: Final[str] = "sqlalchemy rewrite of django-pgtrigger"
__title__: Final[str] = "sqlalchemy-pgtrigger"
__uri__: Final[str] = "https://github.com/jp-zuniga/sqlalchemy-pgtrigger"
__version__: Final[str] = "0.0.0"
