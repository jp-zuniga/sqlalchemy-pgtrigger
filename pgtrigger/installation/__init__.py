"""
Installing, inspecting, and disarming triggers.

Every function takes a connectable first. There is no ambient connection and
nothing installs itself behind your back: either migrations own installation, or
you call one of these.

An `Engine` gets a transaction of its own. A `Connection` or `Session` is used
as given, so the work joins whatever transaction you are already in and rolls
back with it.
"""

from typing import TYPE_CHECKING

from .bind import bind, default_schema
from .introspection import InstalledTrigger, installed, prunable
from .operations import disable, enable, install, prune, uninstall
from .status import TriggerStatus, status

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "InstalledTrigger",
    "TriggerStatus",
    "bind",
    "default_schema",
    "disable",
    "enable",
    "install",
    "installed",
    "prunable",
    "prune",
    "status",
    "uninstall",
)
