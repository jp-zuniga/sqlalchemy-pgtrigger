"""
Constants shared across the package.
"""

import re

from logging import getLogger
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.dialects.postgresql.base import PGDialect

from typing_extensions import Sentinel

if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger
    from re import Pattern
    from typing import Final

    from sqlalchemy import TextClause
    from sqlalchemy.sql.compiler import IdentifierPreparer


########################################################################################

COMMENT_PREFIX: Final[str] = "pgtrigger"
"""
Marker opening the comment written onto every managed trigger.
"""

DIGEST_LENGTH: Final[int] = 5
"""
Characters of the table digest appended to a trigger's PostgreSQL identifier.
"""

DOLLAR_TAG_PATTERN: Final[Pattern] = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
"""
Opening or closing tag of a dollar-quoted string.
"""

DOLLAR_TAG: Final[str] = "$pgtrigger$"
"""
Dollar-quote tag wrapping generated function bodies.

A plain `$$` would be broken by a body that itself contains `$$`.
"""

FUNC_INDENT: Final[int] = 8
"""
Columns a function body is indented by inside the generated `CREATE FUNCTION`.
"""

LISTENER_KEY: Final[str] = "pgtrigger_listener"
"""
Key set in a `Table.info` once its `create_all` listener is registered.

Guards against attaching the same listener twice when a table carries more than
one trigger.
"""

LOGGER: Final[Logger] = getLogger("pgtrigger")
"""
Library logger instance.
"""

MAX_NAME_LENGTH: Final[int] = 47
"""
Longest permissible trigger name.

PostgreSQL identifiers stop at 63 characters. `PGID_PREFIX`, `DIGEST_LENGTH`, and
the separating underscore account for the other 16.
"""

MAX_PGID_LENGTH: Final[int] = 63
"""
Longest PostgreSQL identifier.
"""

NAME_PATTERN: Final[Pattern] = re.compile(r"\A[A-Za-z0-9_-]+\Z")
"""
Characters permitted in a trigger name.

Restricted to what survives PostgreSQL identifier folding unquoted, so that a
trigger can be named in `SET CONSTRAINTS` and in `ALTER TABLE` without quoting.
"""

NEW_ROWS: Final[str] = "new_values"
"""
Default name for the transition table holding rows as they will be.
"""

OLD_ROWS: Final[str] = "old_values"
"""
Default name for the transition table holding rows as they were.
"""

PG_DIALECT: Final[PGDialect] = PGDialect(paramstyle="named")
"""
A DBAPI-less PostgreSQL dialect used to render expressions and identifiers.

`paramstyle="named"` is deliberate. `psycopg` uses `pyformat`, under which
SQLAlchemy's identifier preparer doubles every `%` it renders. Trigger SQL is
executed with no parameters at all, so doubling would corrupt statements like:

```sql
RAISE EXCEPTION 'Cannot delete rows from %.', TG_TABLE_NAME;
```
"""

PGID_PREFIX: Final[str] = "pgtrigger_"
"""
Prefix on every generated PostgreSQL identifier.

Introspection uses it to tell our triggers apart from hand-written ones, so
nothing outside this package is ever dropped or altered.
"""

PREPARER: Final[IdentifierPreparer] = PG_DIALECT.identifier_preparer
"""
PostgreSQL identifier quoting, escaping, and case-folding rules.
"""

READ_SETTING: Final[TextClause] = text("SELECT current_setting(:name, true)")
"""
Read a run-time parameter, yielding `NULL` rather than raising if it is unset.
"""

REQUIRED_TRIGGER_ATTRS: Final[Sequence[str]] = ("name", "time", "events")
"""
Attributes with no default, which every trigger has to supply somehow.
"""

TEMPLATE_VERSION: Final[int] = 1
"""
Version of the installation template.

Written into each trigger's comment so that a future template can recognise,
and deliberately invalidate, triggers installed by an earlier one.
"""

UNSET: Final[Sentinel] = Sentinel("UNSET")
"""
Marker for "no argument supplied", distinct from a supplied `None`.
"""

WILDCARD: Final[str] = ":*"
"""
Suffix selecting every trigger on a table, e.g. `orders:*`.
"""

WRITE_SETTING: Final[TextClause] = text("SELECT set_config(:name, :value, true)")
"""
Write a run-time parameter for the rest of a transaction.
"""

########################################################################################

INSTALLED_SQL: Final[str] = f"""
SELECT
    n.nspname,
    c.relname,
    t.tgname,
    obj_description(t.oid, 'pg_trigger'),
    t.tgenabled
FROM pg_trigger AS t
    JOIN pg_class AS c ON c.oid = t.tgrelid
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE left(t.tgname, {len(PGID_PREFIX)}) = '{PGID_PREFIX}'
    AND NOT t.tgisinternal
    AND t.tgparentid = 0
"""  # ruff: ignore[hardcoded-sql-expression]
"""
Every trigger this package manages.

`left(tgname, n) = '...'` rather than `LIKE 'pgtrigger_%'`, for two reasons: a
literal `%` gets mangled by parameter interpolation, and `_` is a `LIKE`
wildcard, so the obvious pattern would also match names never written.

`tgparentid = 0` skips the copies PostgreSQL clones onto partition children. Those
are managed by the parent and cannot be dropped directly.
"""

REFLECT_SQL: Final[str] = f"""
SELECT
    n.nspname,
    c.relname,
    t.tgname,
    obj_description(t.oid, 'pg_trigger'),
    pg_get_functiondef(t.tgfoid),
    pg_get_triggerdef(t.oid)
FROM pg_trigger AS t
    JOIN pg_class AS c ON c.oid = t.tgrelid
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE left(t.tgname, {len(PGID_PREFIX)}) = '{PGID_PREFIX}'
    AND NOT t.tgisinternal
    AND t.tgparentid = 0
"""  # ruff: ignore[hardcoded-sql-expression]
"""
Managed triggers, with enough of their definition to put them back.
"""
