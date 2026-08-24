"""
Comparing what is declared against what is installed.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pgtrigger.registry

from pgtrigger.enums import TriggerState

from .bind import bind, default_schema
from .introspection import installed

if TYPE_CHECKING:
    from pgtrigger.aliases import Connectable

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
class TriggerStatus:
    """
    How one trigger relates to its declaration.
    """

    uri: str
    pgid: str
    state: TriggerState

    enabled: bool | None
    """
    Whether the trigger is armed, or `None` when it is not installed.
    """

    def __str__(self) -> str:
        """
        Describe the trigger's state, and whether it is armed.

        Returns:
            str: A one-line summary.

        """

        if self.enabled is None:
            return f"{self.uri}: {self.state}"

        return f"{self.uri}: {self.state} ({'on' if self.enabled else 'off'})"


########################################################################################


def status(
    connectable: Connectable,
    *uris: str,
    include_orphans: bool = True,
) -> list[TriggerStatus]:
    """
    Compare what is declared against what is installed.

    A trigger reads as `OUTDATED` when its fingerprint differs from the
    declaration's, and also when its comment is missing or unreadable,
    someone has been editing by hand, and reinstalling is the way back.

    Args:
        connectable: An `Engine`, `Connection`, or `Session`.
        *uris: Triggers to report on. Defaults to all.
        include_orphans: Also report managed triggers that nothing declares any more,
                         as `PRUNE`. Ignored when specific URIs are asked for.

    Returns:
        list[TriggerStatus]: One entry per trigger considered.

    """

    with bind(connectable) as executor:
        present = {trigger.key: trigger for trigger in installed(executor)}
        schema = default_schema(executor)

    results: list[TriggerStatus] = []

    claimed: set[tuple[str, str, str]] = set()

    for registration in pgtrigger.registry.registered(*uris):
        table = registration.table
        key = (table.schema or schema, table.name, registration.pgid)
        claimed.add(key)
        found = present.get(key)

        if found is None:
            state = TriggerState.UNINSTALLED
        elif found.fingerprint == registration.compile().fingerprint:
            state = TriggerState.INSTALLED
        else:
            state = TriggerState.OUTDATED

        results.append(
            TriggerStatus(
                uri=registration.uri,
                pgid=registration.pgid,
                state=state,
                enabled=found.enabled if found else None,
            )
        )

    if include_orphans and not uris:
        results.extend(
            TriggerStatus(
                uri=f"{orphan.schema}.{orphan.table}:{orphan.pgid}",
                pgid=orphan.pgid,
                state=TriggerState.PRUNE,
                enabled=orphan.enabled,
            )
            for key, orphan in present.items()
            if key not in claimed
        )

    return results
