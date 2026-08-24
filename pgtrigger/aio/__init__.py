"""
Async counterparts to everything that touches a connection.

The installation functions are the synchronous ones run through `run_sync`,
since they are a handful of DDL statements and there is nothing to gain from
duplicating them. The runtime functions are written out, because a context
manager cannot hold a greenlet across its `yield`.

```python
from pgtrigger import aio

await aio.install(async_engine)

async with aio.ignore(session, "orders:no_deletes"):
    await session.delete(order)
```
"""

from typing import TYPE_CHECKING

from .bind import require_scoped, run_sync
from .installation import (
    disable,
    enable,
    install,
    installed,
    prunable,
    prune,
    status,
    uninstall,
)
from .runtime import constraints, ignore, ignored, is_ignored

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "constraints",
    "disable",
    "enable",
    "ignore",
    "ignored",
    "install",
    "installed",
    "is_ignored",
    "prunable",
    "prune",
    "require_scoped",
    "run_sync",
    "status",
    "uninstall",
)
