"""
Writing operations out into a revision file.
"""

from typing import TYPE_CHECKING

from alembic.autogenerate import renderers

from .operations import CreatePGTriggerOp, DropPGTriggerOp, RunPGSQLOp

if TYPE_CHECKING:
    from alembic.autogenerate.api import AutogenContext


########################################################################################


def render_sql(sql: str) -> str:
    """
    Render a SQL string into a revision, readably where possible.

    Trigger SQL runs to a couple of dozen lines, and a `repr` of it is a single
    unreadable line. A triple-quoted literal keeps the statement reviewable in
    the revision; this matters because the revision is the thing that will
    actually run.

    The body sits at column zero and the closing quotes follow the last
    character directly, because the literal has to evaluate back to exactly the
    SQL it was given. Indenting it, or padding it out to a tidy closing line,
    would put whitespace into the statement that runs.

    Falls back to `repr` when the SQL contains anything that would break the
    quoting.

    Returns:
        str: A Python expression evaluating to `sql`.

    """

    if '"""' in sql or "\\" in sql or sql.endswith('"'):
        return repr(sql)

    return f'"""\\\n{sql}"""'


########################################################################################


@renderers.dispatch_for(CreatePGTriggerOp)
def render_create_pgtrigger(
    autogen_context: AutogenContext,  # ruff: ignore[unused-function-argument]
    op: CreatePGTriggerOp,
) -> str:
    """
    Render a `CreatePGTriggerOp`.

    Returns:
        str: The call as it appears in the revision.

    """

    lines = [
        "op.create_pgtrigger(",
        f"        pgid={op.pgid!r},",
        f"        table={op.table!r},",
        f"        fingerprint={op.fingerprint!r},",
        f"        sql={render_sql(op.sql)},",
    ]

    if op.reverse_sql:
        lines.append(f"        reverse_sql={render_sql(op.reverse_sql)},")

    lines.append("    )")

    return "\n".join(lines)


@renderers.dispatch_for(DropPGTriggerOp)
def render_drop_pgtrigger(
    autogen_context: AutogenContext,  # ruff: ignore[unused-function-argument]
    op: DropPGTriggerOp,
) -> str:
    """
    Render a `DropPGTriggerOp`.

    Returns:
        str: The call as it appears in the revision.

    """

    lines = [
        "op.drop_pgtrigger(",
        f"        pgid={op.pgid!r},",
        f"        table={op.table!r},",
    ]

    if op.reverse_sql:
        lines.append(f"        reverse_sql={render_sql(op.reverse_sql)},")

    lines.append("    )")

    return "\n".join(lines)


@renderers.dispatch_for(RunPGSQLOp)
def render_run_pgsql(
    autogen_context: AutogenContext,  # ruff: ignore[unused-function-argument]
    op: RunPGSQLOp,
) -> str:
    """
    Render a `RunPGSQLOp`.

    Returns:
        str: The call as it appears in the revision.

    """

    lines = ["op.run_pg_sql(", f"        sql={render_sql(op.sql)},"]

    if op.reverse_sql:
        lines.append(f"        reverse_sql={render_sql(op.reverse_sql)},")

    lines.append("    )")

    return "\n".join(lines)
