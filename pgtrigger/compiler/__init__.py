"""
Declarations reduced to SQL.

Nothing here knows about tables, conditions, or the expression language: by the
time a `Trigger` reaches this package every identifier has been resolved and
quoted, and what is left is text.

That separation is what lets a migration be durable. A revision records the
finished SQL rather than a recipe for producing it, so editing a declaration
or changing the template in this package never rewrites history.
"""

from typing import TYPE_CHECKING

from .comment import format_comment, parse_comment
from .disable import Disable
from .drop import Drop
from .enable import Enable
from .trigger import CompiledTrigger
from .upsert import Upsert

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "CompiledTrigger",
    "Disable",
    "Drop",
    "Enable",
    "Upsert",
    "format_comment",
    "parse_comment",
)
