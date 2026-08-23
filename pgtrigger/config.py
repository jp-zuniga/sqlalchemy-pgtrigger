"""
Package-level configuration.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from typing import Final

########################################################################################


@dataclass(kw_only=True, slots=True)
@final
class Config:
    """
    Runtime configuration.

    Mutate the module-level `CONFIG` before any table is declared:

    ```python
    from pgtrigger import CONFIG

    CONFIG.install_on_create = False
    ```
    """

    ignore_setting: str = "pgtrigger.ignore"
    """
    PostgreSQL run-time parameter naming the triggers to skip.

    Read by every generated trigger function and written by `pgtrigger.ignore`.
    Changing it after triggers are installed leaves them reading the old
    parameter until they are reinstalled.
    """

    install_on_create: bool = True
    """
    Whether `metadata.create_all()` also installs declared triggers.

    Turn it off when migrations own all DDL.
    """

    autogenerate_reverse_sql: bool = True
    """
    Whether autogenerate captures the SQL to restore a dropped or replaced trigger,
    so that `downgrade` runs unaided.
    """


########################################################################################

CONFIG: Final[Config] = Config()
"""
The active configuration.
"""
