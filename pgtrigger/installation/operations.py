"""
Creating, dropping, arming, and disarming triggers.
"""

from typing import TYPE_CHECKING

import pgtrigger.ddl
import pgtrigger.registry

from pgtrigger.consts import LOGGER
from pgtrigger.enums import TriggerInstallOperationVerb

from .bind import bind
from .introspection import prunable

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from pgtrigger.aliases import Connectable
    from pgtrigger.compiler import CompiledTrigger

########################################################################################


def apply(
    *,
    connectable: Connectable,
    render: Callable[[CompiledTrigger], str],
    uris: Sequence[str],
    verb: TriggerInstallOperationVerb,
) -> None:
    """
    Run one piece of a compiled trigger's SQL across a set of registrations.
    """

    with bind(connectable) as executor:
        for registration in pgtrigger.registry.registered(*uris):
            LOGGER.info("pgtrigger: %s %s.", verb, registration.uri)
            pgtrigger.ddl.execute(executor, render(registration.compile()))


########################################################################################


def disable(connectable: Connectable, *uris: str) -> None:
    """
    Stop triggers firing, for everyone.

    Persistent, connection-independent, and it takes an `ACCESS EXCLUSIVE` lock
    on each table. To disable trigger down for a block of code, use `pgtrigger.ignore`.
    """

    apply(
        connectable=connectable,
        render=(lambda trigger: trigger.disable_sql),
        uris=uris,
        verb=TriggerInstallOperationVerb.DISABLE,
    )


def enable(connectable: Connectable, *uris: str) -> None:
    """
    Re-arm triggers that were disabled.
    """

    apply(
        connectable=connectable,
        render=(lambda trigger: trigger.enable_sql),
        uris=uris,
        verb=TriggerInstallOperationVerb.ENABLE,
    )


def install(
    connectable: Connectable,
    *uris: str,
    prune_orphans: bool = False,
) -> None:
    """
    Create or replace triggers.

    Args:
        connectable: An `Engine`, `Connection`, or `Session`.
        *uris: Triggers to install. Defaults to all.
        prune_orphans: Also drop managed triggers nothing declares any more.
                       Only meaningful when installing everything.

    """

    apply(
        connectable=connectable,
        render=(lambda trigger: trigger.install_sql),
        uris=uris,
        verb=TriggerInstallOperationVerb.INSTALL,
    )

    if prune_orphans and not uris:
        prune(connectable)


def uninstall(
    connectable: Connectable,
    *uris: str,
    prune_orphans: bool = False,
) -> None:
    """
    Drop triggers, leaving their functions in place.

    Args:
        connectable: An `Engine`, `Connection`, or `Session`.
        *uris: Triggers to remove. Defaults to all.
        prune_orphans: Also drop managed triggers nothing declares any more.

    """

    apply(
        connectable=connectable,
        render=(lambda trigger: trigger.uninstall_sql),
        uris=uris,
        verb=TriggerInstallOperationVerb.UNINSTALL,
    )

    if prune_orphans and not uris:
        prune(connectable)


########################################################################################


def prune(connectable: Connectable) -> None:
    """
    Drop managed triggers that no longer have a declaration.

    This is how a trigger deleted from a model gets deleted from the database.
    Only triggers carrying our identifier prefix are considered.
    """

    with bind(connectable) as executor:
        for orphan in prunable(executor):
            LOGGER.info("pgtrigger: pruning %s.", orphan)
            pgtrigger.ddl.execute(
                executor,
                f"DROP TRIGGER IF EXISTS {orphan.pgid} ON {orphan.qualified_table};",
            )
