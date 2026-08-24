"""
The statements that install a trigger.
"""

from dataclasses import dataclass, field
from textwrap import indent
from typing import TYPE_CHECKING, override

from pgtrigger.config import CONFIG
from pgtrigger.consts import DOLLAR_TAG, FUNC_INDENT
from pgtrigger.core import Event, ForEach, Statement
from pgtrigger.utils import hex_digest, quote_literal

from .comment import format_comment

if TYPE_CHECKING:
    from typing import Final, Literal

    from pgtrigger.core import Execution, Time


########################################################################################

FIELD_OPTIONS: Final[dict[Literal["compare", "init", "repr"], bool]] = {
    "compare": False,
    "init": False,
    "repr": False,
}
"""
Field options for a value assembled in `__post_init__`.
"""

########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
class Upsert(Statement):
    """
    The statements that create a trigger and the function behind it.

    Every field arrives already rendered and quoted; this only assembles them.

    Field order follows the `CREATE TRIGGER` grammar.

    The derived fields below `ignore_setting` are built once,
    in `__post_init__`, rather than on each read.
    """

    pgid: str
    """
    PostgreSQL identifier shared by the trigger and its function.
    """

    table: str
    """
    Quoted, schema-qualified table the trigger is attached to.
    """

    func: str
    """
    `PL/pgSQL` between `BEGIN` and `END`.
    """

    time: Time
    """
    Whether the trigger runs before, after, or instead of the statement.
    """

    events: str
    """
    Rendered event list, e.g. `INSERT OR UPDATE OF "status"`.
    """

    for_each: ForEach = ForEach.ROW
    """
    Whether the trigger fires per row or per statement.
    """

    declare: str = ""
    """
    Rendered `DECLARE` block, or empty.
    """

    execution: Execution | None = None
    """
    Deferrability.
    `None` leaves the clause off,
    which PostgreSQL reads as `NOT DEFERRABLE`.
    """

    referencing: str = ""
    """
    Rendered `REFERENCING` clause, or empty.
    """

    condition: str = ""
    """
    Rendered `WHEN (...)` clause, or empty.
    """

    ignore_setting: str = ""
    """
    Run-time parameter the trigger consults to see if it should stand down.

    Defaults to whatever `CONFIG.ignore_setting` holds when this is built.
    """

    function: str = field(default="", **FIELD_OPTIONS)
    """
    The `CREATE OR REPLACE FUNCTION` statement.
    """

    trigger: str = field(default="", **FIELD_OPTIONS)
    """
    The statements that drop and recreate the trigger itself.
    """

    definition: str = field(default="", **FIELD_OPTIONS)
    """
    Everything but the comment.

    This is what gets fingerprinted, so a change to the function, the condition,
    the events, or anything else about the trigger shows up as drift. The
    comment is excluded because it carries the fingerprint.
    """

    fingerprint: str = field(default="", **FIELD_OPTIONS)
    """
    Digest of the definition, stored in the trigger's comment.
    """

    comment: str = field(default="", **FIELD_OPTIONS)
    """
    The `pgtrigger:<version>:<fingerprint>` marker written onto the trigger.
    """

    sql: str = field(default="", **FIELD_OPTIONS)
    """
    The full installation script: function, trigger, and comment.
    """

    def __post_init__(self) -> None:
        """
        Check the body, then assemble every derived value in dependency order.

        Raises:
            ValueError: The body contains the dollar-quote tag wrapping it.

        """

        if DOLLAR_TAG in self.func or DOLLAR_TAG in self.declare:
            raise ValueError(
                f"A trigger function body cannot contain {DOLLAR_TAG}, which"
                " terminates the quoting around it."
            )

        if not self.ignore_setting:
            self._set("ignore_setting", CONFIG.ignore_setting)

        self._set("function", self._render_function())
        self._set("trigger", self._render_trigger())
        self._set("definition", f"{self.function}\n\n{self.trigger}")
        self._set("fingerprint", hex_digest(value=self.definition))
        self._set("comment", format_comment(self.fingerprint))
        self._set("sql", self._render_sql())

    @override
    def __str__(self) -> str:
        """
        Render the full installation script.

        Returns:
            str: Function, trigger, and comment.

        """

        return self.sql

    def _set(self, name: str, value: str) -> None:
        """
        Assign a field on a frozen instance.

        `__post_init__` is the one place this is legitimate: the object is not
        yet visible to anyone else, and every value written here is a pure
        function of fields that are already set.
        """

        object.__setattr__(self, name, value)  # ruff: ignore[unnecessary-dunder-call]

    def _render_function(self) -> str:
        """
        Render the `CREATE OR REPLACE FUNCTION` statement.

        The body opens by consulting the ignore parameter, so `pgtrigger.ignore`
        can stand the trigger down for one transaction. Two-argument
        `CURRENT_SETTING` yields `NULL` rather than raising when the parameter
        was never set, and `NULLIF` covers one that was set and then blanked.

        Returns:
            str: The function definition.

        """

        # a statement-level trigger has no row to hand back,
        # and OLD and NEW go unassigned there in any case
        stand_down = (
            "RETURN NULL;"
            if self.for_each is ForEach.STATEMENT
            else (
                f"IF TG_OP = '{Event.DELETE}' THEN RETURN OLD; ELSE RETURN NEW; END IF;"
            )
        )

        setting = quote_literal(self.ignore_setting)

        body = [
            f"CREATE OR REPLACE FUNCTION {self.pgid}()",
            "RETURNS TRIGGER",
            "LANGUAGE plpgsql",
            f"AS {DOLLAR_TAG}",
        ]

        if self.declare:
            body.append(f"    {self.declare}")

        body += [
            "    BEGIN",
            "        IF COALESCE(",
            "            TG_NAME = ANY(",
            f"                NULLIF(CURRENT_SETTING({setting}, TRUE), '')::TEXT[]",
            "            ),",
            "            FALSE",
            "        ) THEN",
            f"            {stand_down}",
            "        END IF;",
            "",
            indent(self.func, " " * FUNC_INDENT),
            "    END;",
            f"{DOLLAR_TAG};",
        ]

        return "\n".join(body)

    def _render_trigger(self) -> str:
        """
        Render the statements that drop and recreate the trigger itself.

        `DROP` then `CREATE`, rather than PG14's `CREATE OR REPLACE TRIGGER`,
        because a replace cannot turn a plain trigger into a constraint trigger
        or back. Both run inside one transaction, and the drop takes an
        `ACCESS EXCLUSIVE` lock held until commit, so no statement ever observes
        the table without its trigger.

        Returns:
            str: The drop and create statements.

        """

        constraint = "CONSTRAINT " if self.deferrable else ""

        parts = [
            f"CREATE {constraint}TRIGGER {self.pgid}",
            f"    {self.time} {self.events} ON {self.table}",
        ]

        if self.execution is not None:
            parts.append(f"    {self.execution.clause}")

        if self.referencing:
            parts.append(f"    {self.referencing}")

        parts.append(f"    FOR EACH {self.for_each}")

        if self.condition:
            parts.append(f"    {self.condition}")

        parts.append(f"    EXECUTE FUNCTION {self.pgid}();")

        create = "\n".join(parts)

        return f"DROP TRIGGER IF EXISTS {self.pgid} ON {self.table};\n\n{create}"

    def _render_sql(self) -> str:
        """
        Render the definition, followed by the comment carrying its fingerprint.

        Returns:
            str: Function, trigger, and comment.

        """

        comment = (
            f"COMMENT ON TRIGGER {self.pgid} ON {self.table}"
            f" IS {quote_literal(self.comment)};"
        )

        return f"{self.definition}\n\n{comment}"

    @property
    def deferrable(self) -> bool:
        """
        Report whether this is a constraint trigger.

        Returns:
            bool: `True` when the trigger's firing can be postponed.

        """

        return self.execution is not None and self.execution.deferrable
