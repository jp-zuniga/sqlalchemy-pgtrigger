"""
Rendering operations into a revision, and reversing them.
"""

import ast

import hypothesis as ht
import pytest

from pgtrigger.migrations.operations import (
    CreatePGTriggerOp,
    DropPGTriggerOp,
    RunPGSQLOp,
)
from pgtrigger.migrations.reflection import Reflected
from pgtrigger.migrations.rendering import (
    render_create_pgtrigger,
    render_drop_pgtrigger,
    render_run_pgsql,
    render_sql,
)

from .strategies import identifiers, sql_text

########################################################################################


def evaluate(source: str) -> dict[str, object]:
    captured: dict[str, object] = {}

    class Op:
        create_pgtrigger = staticmethod(lambda **kwargs: captured.update(kwargs))
        drop_pgtrigger = staticmethod(lambda **kwargs: captured.update(kwargs))
        run_pgsql = staticmethod(lambda **kwargs: captured.update(kwargs))

    ast.parse(f"def upgrade() -> None:\n    {source}")

    exec(source, {"op": Op})  # ruff: ignore[exec-builtin]

    return captured


########################################################################################


class TestRenderSql:
    def test_prefers_a_readable_literal(self) -> None:
        # the revision is what actually runs, so it has to stay reviewable
        assert render_sql("SELECT 1;\nSELECT 2;").startswith('"""')

    def test_falls_back_for_triple_quotes(self) -> None:
        assert render_sql('a """ b').startswith("'")

    def test_falls_back_for_backslashes(self) -> None:
        assert not render_sql("a \\ b").startswith('"""')

    @pytest.mark.parametrize("value", ["a\rb", "a\x00b", 'ab"'])
    def test_falls_back_for_what_the_tokenizer_mangles(self, value: str) -> None:
        assert eval(render_sql(value)) == value  # ruff: ignore[suspicious-eval-usage]

    @ht.given(sql=sql_text)
    def test_always_evaluates_back_to_the_original(self, sql: str) -> None:
        assert eval(render_sql(sql)) == sql  # ruff: ignore[suspicious-eval-usage]

    @ht.given(sql=sql_text)
    def test_always_produces_a_single_expression(self, sql: str) -> None:
        assert isinstance(ast.parse(render_sql(sql), mode="eval"), ast.Expression)


########################################################################################


class TestRenderOperations:
    def test_create_round_trips(self) -> None:
        op = CreatePGTriggerOp(
            pgid="pgtrigger_t_abcde",
            table="orders",
            sql="CREATE OR REPLACE FUNCTION f();",
            fingerprint="abc",
        )

        # ty: ignore[invalid-argument-type]
        captured = evaluate(render_create_pgtrigger(None, op))

        assert captured == {
            "pgid": op.pgid,
            "table": op.table,
            "fingerprint": op.fingerprint,
            "sql": op.sql,
        }

    def test_create_includes_reverse_sql_when_present(self) -> None:
        op = CreatePGTriggerOp(pgid="p", table="orders", sql="A;", reverse_sql="B;")

        # ty: ignore[invalid-argument-type]
        assert evaluate(render_create_pgtrigger(None, op))["reverse_sql"] == "B;"

    def test_create_omits_reverse_sql_when_absent(self) -> None:
        op = CreatePGTriggerOp(pgid="p", table="orders", sql="A;")

        # ty: ignore[invalid-argument-type]
        assert "reverse_sql" not in evaluate(render_create_pgtrigger(None, op))

    def test_drop_round_trips(self) -> None:
        op = DropPGTriggerOp(pgid="p", table="orders", reverse_sql="B;")

        # ty: ignore[invalid-argument-type]
        captured = evaluate(render_drop_pgtrigger(None, op))

        assert captured == {"pgid": "p", "table": "orders", "reverse_sql": "B;"}

    def test_run_round_trips(self) -> None:
        op = RunPGSQLOp(sql="A;", reverse_sql="B;")

        # ty: ignore[invalid-argument-type]
        assert evaluate(render_run_pgsql(None, op)) == {
            "sql": "A;",
            "reverse_sql": "B;",
        }

    @ht.given(pgid=identifiers, table=identifiers, sql=sql_text)
    def test_any_create_round_trips(self, pgid: str, table: str, sql: str) -> None:
        op = CreatePGTriggerOp(pgid=pgid, table=table, sql=sql, fingerprint="abc")

        # ty: ignore[invalid-argument-type]
        captured = evaluate(render_create_pgtrigger(None, op))

        assert captured["sql"] == sql
        assert captured["pgid"] == pgid
        assert captured["table"] == table


########################################################################################


class TestReverse:
    def test_create_without_capture_reverses_to_a_drop(self) -> None:
        op = CreatePGTriggerOp(pgid="p", table="orders", sql="A;")
        reversed_op = op.reverse()

        assert isinstance(reversed_op, DropPGTriggerOp)
        assert reversed_op.pgid == "p"

    def test_create_with_capture_restores_the_previous_trigger(self) -> None:
        op = CreatePGTriggerOp(pgid="p", table="orders", sql="A;", reverse_sql="B;")
        reversed_op = op.reverse()

        assert isinstance(reversed_op, RunPGSQLOp)
        assert reversed_op.sql == "B;"

    def test_drop_with_capture_restores(self) -> None:
        op = DropPGTriggerOp(pgid="p", table="orders", reverse_sql="B;")
        reversed_op = op.reverse()

        assert isinstance(reversed_op, RunPGSQLOp)
        assert reversed_op.sql == "B;"

    def test_drop_without_capture_says_why_it_cannot(self) -> None:
        with pytest.raises(NotImplementedError, match="no reverse SQL was captured"):
            DropPGTriggerOp(pgid="p", table="orders").reverse()

    def test_run_without_capture_says_why_it_cannot(self) -> None:
        with pytest.raises(NotImplementedError, match="no reverse_sql"):
            RunPGSQLOp(sql="A;").reverse()

    def test_run_reverses_to_its_reverse(self) -> None:
        reversed_op = RunPGSQLOp(sql="A;", reverse_sql="B;").reverse()

        assert isinstance(reversed_op, RunPGSQLOp)
        assert reversed_op.sql == "B;"


########################################################################################


class TestReflected:
    def build(self, **kwargs) -> Reflected:  # ruff: ignore[missing-type-kwargs]
        return Reflected(**{
            "schema": "public",
            "table": "orders",
            "pgid": "pgtrigger_t_abcde",
            "comment": "pgtrigger:1:abc",
            "function_sql": "CREATE OR REPLACE FUNCTION f() ...",
            "trigger_sql": "CREATE TRIGGER t ...",
            **kwargs,
        })

    def test_key_identifies_it(self) -> None:
        assert self.build().key == ("public", "orders", "pgtrigger_t_abcde")

    def test_fingerprint_comes_from_the_comment(self) -> None:
        assert self.build().fingerprint == "abc"

    def test_unrecognised_comment_has_no_fingerprint(self) -> None:
        assert self.build(comment="hand written").fingerprint is None

    def test_restore_sql_puts_the_comment_back(self) -> None:
        # otherwise autogenerate reports drift on the restored trigger
        restored = self.build().restore_sql

        assert "COMMENT ON TRIGGER" in restored
        assert "'pgtrigger:1:abc'" in restored

    def test_restore_sql_qualifies_the_table(self) -> None:
        assert "public.orders" in self.build().restore_sql

    def test_restore_sql_omits_an_absent_comment(self) -> None:
        assert "COMMENT ON TRIGGER" not in self.build(comment=None).restore_sql

    def test_restore_sql_does_not_double_the_terminator(self) -> None:
        restored = self.build(function_sql="CREATE FUNCTION f();").restore_sql

        assert ";;" not in restored
