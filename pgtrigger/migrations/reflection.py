"""
Reading installed triggers back, with enough detail to restore them.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from pgtrigger.compiler import parse_comment
from pgtrigger.consts import REFLECT_SQL
from pgtrigger.utils import quote, quote_literal

if TYPE_CHECKING:
    from sqlalchemy import Connection


########################################################################################


@dataclass(frozen=True, kw_only=True, slots=True)
class Reflected:
    """
    A managed trigger read out of the database, with its source.
    """

    schema: str
    table: str
    pgid: str
    comment: str | None
    function_sql: str
    trigger_sql: str

    @property
    def fingerprint(self) -> str | None:
        """
        Read the digest recorded in the trigger's comment.

        Returns:
            str | None: The digest, or `None` if the comment is not ours.

        """

        parsed = parse_comment(self.comment)

        return parsed[1] if parsed else None

    @property
    def key(self) -> tuple[str, str, str]:
        """
        Identify this trigger within the database.

        Returns:
            tuple[str, str, str]: Schema, table, and identifier.

        """

        return (self.schema, self.table, self.pgid)

    @property
    def restore_sql(self) -> str:
        """
        Render SQL putting this trigger back exactly as it is now.

        Captured before a drop or a replacement so the downgrade runs unaided.
        The comment goes back too, so autogenerate does not then see the
        restored trigger as drifted.

        Returns:
            str: Function, trigger, and comment.

        """

        qualified = f"{quote(self.schema)}.{quote(self.table)}"
        parts = [
            f"{self.function_sql.rstrip().rstrip(';')};",
            f"{self.trigger_sql};",
        ]

        if self.comment is not None:
            parts.append(
                f"COMMENT ON TRIGGER {self.pgid} ON {qualified}"
                f" IS {quote_literal(self.comment)};"
            )

        return "\n".join(parts)


########################################################################################


def reflect(connection: Connection) -> list[Reflected]:
    """
    Read every managed trigger out of the database.

    Returns:
        list[Reflected]: What is installed, with its source.

    """

    return [
        Reflected(
            schema=row[0],
            table=row[1],
            pgid=row[2],
            comment=row[3],
            function_sql=row[4],
            trigger_sql=row[5],
        )
        for row in connection.execute(text(REFLECT_SQL)).fetchall()
    ]
