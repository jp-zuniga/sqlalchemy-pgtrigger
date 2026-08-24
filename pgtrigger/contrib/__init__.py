"""
Triggers for common requirements.

Each is an ordinary `Trigger` subclass that sets some defaults and overrides a
hook or two, so they double as worked examples of how to build your own.
"""

from typing import TYPE_CHECKING

from .conditions import AllChange, AllDontChange, AnyChange, AnyDontChange, Change
from .protect import Protect
from .readonly import ReadOnly
from .softdelete import SoftDelete

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "AllChange",
    "AllDontChange",
    "AnyChange",
    "AnyDontChange",
    "Change",
    "Protect",
    "ReadOnly",
    "SoftDelete",
)
