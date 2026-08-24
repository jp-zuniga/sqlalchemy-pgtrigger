"""
Async installation.
"""

from typing import TYPE_CHECKING

import pgtrigger.installation

from .bind import run_sync

if TYPE_CHECKING:
    from pgtrigger.aliases import AsyncConnectable
    from pgtrigger.installation import InstalledTrigger, TriggerStatus

########################################################################################


async def disable(connectable: AsyncConnectable, *uris: str) -> None:
    """
    Stop triggers firing, for everyone.
    """

    await run_sync(
        connectable,
        lambda sync: pgtrigger.installation.disable(sync, *uris),
    )


async def enable(connectable: AsyncConnectable, *uris: str) -> None:
    """
    Re-arm triggers that were disabled.
    """

    await run_sync(connectable, lambda sync: pgtrigger.installation.enable(sync, *uris))


async def install(
    connectable: AsyncConnectable,
    *uris: str,
    prune_orphans: bool = False,
) -> None:
    """
    Create or replace triggers. See `pgtrigger.install`.
    """

    await run_sync(
        connectable,
        lambda sync: pgtrigger.installation.install(
            sync,
            *uris,
            prune_orphans=prune_orphans,
        ),
    )


async def installed(connectable: AsyncConnectable) -> list[InstalledTrigger]:
    """
    List every managed trigger present in the database.

    Returns:
        list[InstalledTrigger]: What is actually installed.

    """

    return await run_sync(connectable, pgtrigger.installation.installed)


async def prune(connectable: AsyncConnectable) -> None:
    """
    Drop managed triggers that no longer have a declaration.
    """

    await run_sync(connectable, pgtrigger.installation.prune)


async def prunable(connectable: AsyncConnectable) -> list[InstalledTrigger]:
    """
    List managed triggers with no corresponding declaration.

    Returns:
        list[InstalledTrigger]: What `prune` would drop.

    """

    return await run_sync(connectable, pgtrigger.installation.prunable)


async def status(
    connectable: AsyncConnectable,
    *uris: str,
    include_orphans: bool = True,
) -> list[TriggerStatus]:
    """
    Compare what is declared against what is installed.

    Returns:
        list[TriggerStatus]: One entry per trigger considered.

    """

    return await run_sync(
        connectable,
        lambda sync: pgtrigger.installation.status(
            sync,
            *uris,
            include_orphans=include_orphans,
        ),
    )


async def uninstall(
    connectable: AsyncConnectable,
    *uris: str,
    prune_orphans: bool = False,
) -> None:
    """
    Drop triggers. See `pgtrigger.uninstall`.
    """

    await run_sync(
        connectable,
        lambda sync: pgtrigger.installation.uninstall(
            sync,
            *uris,
            prune_orphans=prune_orphans,
        ),
    )
