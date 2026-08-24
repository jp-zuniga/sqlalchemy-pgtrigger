"""
Alembic integration.

Import this from your `env.py` and everything below switches on:

```python
import pgtrigger.migrations  # noqa: F401
```

That registers three operations and makes `autogenerate` aware of them:
`op.create_pgtrigger`, `op.drop_pgtrigger`, and `op.run_pg_sql`.

Alembic keeps no model state, so there is nothing to diff a declaration against
except the database itself. Each installed trigger carries a fingerprint of its
own definition in a comment, so a changed declaration shows up as a difference
without a state file, and so does a trigger somebody edited by hand.

A revision records the finished SQL rather than a recipe for producing it. Edit
a declaration afterwards, or change the template in this package, and the
revision keeps doing exactly what it did the day it was written.
"""

# ruff: ignore[non-empty-init-module]
try:
    # ruff: ignore[unused-import]
    import alembic
except ImportError as i:
    raise RuntimeError("pgtrigger.migrations requires an alembic installation.") from i

########################################################################################

from typing import TYPE_CHECKING

from . import autogenerate, rendering
from .operations import CreatePGTriggerOp, DropPGTriggerOp, RunPGSQLOp, emit
from .reflection import Reflected, reflect
from .schema import temporarily_drop_triggers

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "CreatePGTriggerOp",
    "DropPGTriggerOp",
    "Reflected",
    "RunPGSQLOp",
    "autogenerate",
    "emit",
    "reflect",
    "rendering",
    "temporarily_drop_triggers",
)
