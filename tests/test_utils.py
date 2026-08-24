"""
Quoting, digests, and SQL text handling.
"""

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from sqlalchemy import Column, Integer, MetaData, Table

from pgtrigger.utils.columns import pk_columns, resolve_column, resolve_columns
from pgtrigger.utils.quoting import quote, quote_column, quote_literal, quote_table
from pgtrigger.utils.sql import dedent_sql, split_statements
from pgtrigger.utils.text import hex_digest, table_uri

from .conftest import build_orders
from .strategies import sql_text, statements

########################################################################################


class TestQuoting:
    def test_leaves_plain_identifiers_bare(self) -> None:
        assert quote("orders") == "orders"

    def test_quotes_reserved_words(self) -> None:
        assert quote("order") == '"order"'

    def test_quotes_mixed_case(self) -> None:
        assert quote("Status") == '"Status"'

    def test_table_omits_default_schema(self, orders: Table) -> None:
        assert quote_table(orders) == "orders"

    def test_table_includes_named_schema(self, scoped: Table) -> None:
        assert quote_table(scoped) == "billing.invoices"

    def test_column_uses_database_name_not_key(self, quoted: Table) -> None:
        # the column is keyed `status` but named `Status`
        assert quote_column(quoted.columns["status"]) == '"Status"'

    @ht.given(value=st.text())
    def test_literal_doubles_every_embedded_quote(self, value: str) -> None:
        rendered = quote_literal(value)

        assert rendered.startswith("'")
        assert rendered.endswith("'")
        assert rendered[1:-1].replace("''", "").count("'") == 0

    @ht.given(value=st.text())
    def test_literal_round_trips(self, value: str) -> None:
        assert quote_literal(value)[1:-1].replace("''", "'") == value


########################################################################################


class TestDigest:
    @ht.given(value=st.text())
    def test_is_deterministic(self, value: str) -> None:
        assert hex_digest(value=value) == hex_digest(value=value)

    def test_defaults_to_the_whole_digest(self) -> None:
        # ruff: ignore[magic-value-comparison]
        # a shortened fingerprint would let a changed trigger read as unchanged
        assert len(hex_digest(value="x")) == 64

    @ht.given(value=st.text(), length=st.integers(min_value=1, max_value=64))
    def test_truncates_to_length(self, value: str, length: int) -> None:
        assert len(hex_digest(length=length, value=value)) == length

    @ht.given(value=st.text(), length=st.integers(min_value=1, max_value=64))
    def test_truncation_is_a_prefix(self, value: str, length: int) -> None:
        assert hex_digest(value=value).startswith(
            hex_digest(length=length, value=value)
        )

    @ht.given(left=st.text(), right=st.text())
    def test_distinguishes_different_input(self, left: str, right: str) -> None:
        ht.assume(left != right)

        assert hex_digest(value=left) != hex_digest(value=right)

    @ht.given(value=st.text())
    def test_is_hexadecimal(self, value: str) -> None:
        assert set(hex_digest(value=value)) <= set("0123456789abcdef")


########################################################################################


class TestTableUri:
    def test_omits_absent_schema(self, orders: Table) -> None:
        assert table_uri(orders) == "orders"

    def test_includes_present_schema(self, scoped: Table) -> None:
        assert table_uri(scoped) == "billing.invoices"

    def test_is_unquoted(self, quoted: Table) -> None:
        # the URI names the trigger to a human, not to PostgreSQL
        assert table_uri(quoted) == "order"


########################################################################################


class TestDedentSql:
    def test_strips_common_indentation(self) -> None:
        assert dedent_sql("\n    SELECT 1;\n    SELECT 2;\n") == "SELECT 1;\nSELECT 2;"

    def test_keeps_relative_indentation(self) -> None:
        assert dedent_sql("\n  a\n    b\n") == "a\n  b"

    def test_drops_blank_lines(self) -> None:
        # an empty template placeholder must not leave a line of spaces behind
        assert dedent_sql("a\n   \n\nb") == "a\nb"

    @ht.given(value=sql_text)
    def test_is_idempotent(self, value: str) -> None:
        once = dedent_sql(value)

        assert dedent_sql(once) == once

    @ht.given(value=sql_text)
    def test_leaves_no_trailing_whitespace(self, value: str) -> None:
        assert all(line == line.rstrip() for line in dedent_sql(value).splitlines())

    @ht.given(value=sql_text)
    def test_leaves_no_blank_lines(self, value: str) -> None:
        assert all(line.strip() for line in dedent_sql(value).splitlines())


########################################################################################


class TestSplitStatements:
    @pytest.mark.parametrize(
        ("script", "expected"),
        [
            ([], ""),
            ([], ";;;"),
            ([], "   "),
            (["SELECT 1"], "SELECT 1"),
            (["SELECT 1"], "SELECT 1;"),
            (["SELECT 1", "SELECT 2"], "SELECT 1; SELECT 2;"),
        ],
    )
    def test_simple_scripts(self, expected: list[str], script: str) -> None:
        assert split_statements(script) == expected

    def test_keeps_dollar_quoted_bodies_whole(self) -> None:
        script = "CREATE FUNCTION f() AS $x$ BEGIN; RAISE '%'; END; $x$; SELECT 1;"

        assert split_statements(script) == [
            "CREATE FUNCTION f() AS $x$ BEGIN; RAISE '%'; END; $x$",
            "SELECT 1",
        ]

    def test_ignores_semicolons_inside_string_literals(self) -> None:
        assert split_statements("SELECT 'a;b'; SELECT 2;") == [
            "SELECT 'a;b'",
            "SELECT 2",
        ]

    def test_handles_doubled_quotes_inside_literals(self) -> None:
        assert split_statements("SELECT 'it''s; here'; SELECT 2;") == [
            "SELECT 'it''s; here'",
            "SELECT 2",
        ]

    def test_ignores_semicolons_inside_quoted_identifiers(self) -> None:
        assert split_statements('SELECT "a;b"; SELECT 2;') == [
            'SELECT "a;b"',
            "SELECT 2",
        ]

    def test_ignores_semicolons_inside_line_comments(self) -> None:
        assert split_statements("-- a; b\nSELECT 1;") == ["-- a; b\nSELECT 1"]

    def test_ignores_semicolons_inside_block_comments(self) -> None:
        assert split_statements("/* a; b */ SELECT 1;") == ["/* a; b */ SELECT 1"]

    def test_tolerates_an_unterminated_dollar_quote(self) -> None:
        # malformed input should not hang or raise, just yield what is there
        assert split_statements("SELECT $x$ unterminated") == [
            "SELECT $x$ unterminated"
        ]

    @ht.given(bodies=statements)
    def test_recovers_the_statements_it_was_given(self, bodies: list[str]) -> None:
        stripped = [body.strip() for body in bodies if body.strip()]

        assert split_statements(";".join(stripped)) == stripped

    @ht.given(value=sql_text)
    def test_never_yields_a_blank_statement(self, value: str) -> None:
        assert all(statement.strip() for statement in split_statements(value))

    @ht.given(value=sql_text)
    def test_is_idempotent_on_a_single_statement(self, value: str) -> None:
        split = split_statements(value)

        ht.assume(len(split) == 1)

        assert split_statements(split[0]) == split


########################################################################################


class TestColumns:
    def test_resolves_by_orm_key(self, quoted: Table) -> None:
        assert resolve_column("status", quoted).name == "Status"

    def test_resolves_by_database_name(self, quoted: Table) -> None:
        assert resolve_column("Status", quoted).key == "status"

    def test_passes_a_column_through(self, orders: Table) -> None:
        column = orders.columns["total"]

        assert resolve_column(column, orders) is column

    def test_rejects_an_unknown_name(self, orders: Table) -> None:
        with pytest.raises(ValueError, match="does not resolve to a column"):
            resolve_column("nope", orders)

    def test_lists_available_columns_in_the_error(self, orders: Table) -> None:
        with pytest.raises(ValueError, match="total"):
            resolve_column("nope", orders)

    @ht.given(names=st.lists(st.sampled_from(["id", "status", "total"])))
    def test_resolves_many_in_order(self, names: list[str]) -> None:
        table = build_orders()

        assert [column.key for column in resolve_columns(names, table)] == names

    def test_primary_key_single(self, orders: Table) -> None:
        assert [column.key for column in pk_columns(orders)] == ["id"]

    def test_primary_key_composite_keeps_order(self, composite: Table) -> None:
        assert [column.key for column in pk_columns(composite)] == ["order_id", "leg"]

    def test_primary_key_absent_is_an_error(self) -> None:
        table = Table("keyless", MetaData(), Column("a", Integer))

        with pytest.raises(ValueError, match="no primary key"):
            pk_columns(table)
