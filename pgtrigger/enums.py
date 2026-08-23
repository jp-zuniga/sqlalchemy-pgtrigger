"""
Package-wide enumerations.
"""

from enum import StrEnum
from typing import final

########################################################################################


@final
class LogicalOperator(StrEnum):
    """
    SQL operators used to join or negate parts of a condition.
    """

    AND = "AND"
    IS_DISTINCT = "IS DISTINCT FROM"
    NOT = "NOT"
    NOT_DISTINCT = "IS NOT DISTINCT FROM"
    OR = "OR"


########################################################################################


@final
class TransitionTable(StrEnum):
    """
    Names PostgreSQL binds to the rows visible inside a trigger function.
    """

    NEW = "NEW"
    OLD = "OLD"


########################################################################################


@final
class TriggerInstallOperationVerb(StrEnum):
    """
    Logged operations performed by `pgtrigger.installation`.
    """

    DISABLE = "disable"
    ENABLE = "enable"
    INSTALL = "installing"
    UNINSTALL = "uninstalling"


########################################################################################


@final
class TriggerState(StrEnum):
    """
    How a trigger in the database relates to its declaration.
    """

    INSTALLED = "INSTALLED"
    """
    Present, and its digest matches the declaration.
    """

    OUTDATED = "OUTDATED"
    """
    Present, but the declaration has changed since it was installed.
    """

    PRUNE = "PRUNE"
    """
    Present and managed, but nothing declares it any more.
    """

    UNINSTALLED = "UNINSTALLED"
    """
    Declared, but absent from the database.
    """
