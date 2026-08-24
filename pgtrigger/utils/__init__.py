"""
Low-level helpers shared across the package.
"""

from typing import TYPE_CHECKING

from .columns import pk_columns, resolve_column, resolve_columns
from .quoting import quote, quote_column, quote_literal, quote_table
from .sql import compile_expression, consume_quoted, dedent_sql, split_statements
from .text import hex_digest, table_uri

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################

__all__: Final[Sequence[str]] = (
    "compile_expression",
    "consume_quoted",
    "dedent_sql",
    "hex_digest",
    "pk_columns",
    "quote",
    "quote_column",
    "quote_literal",
    "quote_table",
    "resolve_column",
    "resolve_columns",
    "split_statements",
    "table_uri",
)
