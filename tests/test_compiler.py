"""
Declarations reduced to SQL.
"""

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.compiler.comment import format_comment, parse_comment
from pgtrigger.compiler.disable import Disable
from pgtrigger.compiler.drop import Drop
from pgtrigger.compiler.enable import Enable
from pgtrigger.compiler.trigger import CompiledTrigger
from pgtrigger.compiler.upsert import Upsert
from pgtrigger.consts import COMMENT_PREFIX, DOLLAR_TAG, TEMPLATE_VERSION
from pgtrigger.core.clauses import Event, Execution, ForEach, Time
from pgtrigger.utils.sql import split_statements

from .strategies import identifiers

if TYPE_CHECKING:
    from pgtrigger.core import Statement

########################################################################################


def build_upsert(**kwargs) -> Upsert:  # ruff: ignore[missing-type-kwargs]
    # ty: ignore[invalid-argument-type]
    return Upsert(**{
        "pgid": "pgtrigger_t_abcde",
        "table": "orders",
        "func": "RETURN OLD;",
        "time": Time.BEFORE,
        "events": Event.DELETE,
        **kwargs,
    })


########################################################################################


class TestComment:
    def test_format_carries_prefix_and_version(self) -> None:
        assert format_comment("abc") == f"{COMMENT_PREFIX}:{TEMPLATE_VERSION}:abc"

    @ht.given(fingerprint=st.from_regex(r"\A[0-9a-f]{1,64}\Z"))
    def test_round_trips(self, fingerprint: str) -> None:
        assert parse_comment(format_comment(fingerprint)) == (
            TEMPLATE_VERSION,
            fingerprint,
        )

    @pytest.mark.parametrize(
        "comment",
        [
            None,
            "",
            "something else",
            "pgtrigger:",
            "pgtrigger:abc",
            "other:1:abc",
        ],
    )
    def test_unrecognised_comments_read_as_none(self, comment: str | None) -> None:
        # a comment somebody replaced by hand must not parse as a mismatch
        assert parse_comment(comment) is None

    @ht.given(comment=st.text())
    def test_never_raises(self, comment: str) -> None:
        parse_comment(comment)


########################################################################################


class TestSimpleStatements:
    def test_drop_is_conditional(self) -> None:
        assert Drop(pgid="p", table="orders").sql == (
            "DROP TRIGGER IF EXISTS p ON orders;"
        )

    def test_enable(self) -> None:
        assert Enable(pgid="p", table="orders").sql == (
            "ALTER TABLE orders ENABLE TRIGGER p;"
        )

    def test_disable(self) -> None:
        assert Disable(pgid="p", table="orders").sql == (
            "ALTER TABLE orders DISABLE TRIGGER p;"
        )

    @pytest.mark.parametrize("statement", [Disable, Drop, Enable])
    def test_str_is_the_sql(self, statement: type[Statement]) -> None:
        # ty: ignore[unknown-argument]
        built = statement(pgid="p", table="orders")

        assert str(built) == built.sql

    @pytest.mark.parametrize("statement", [Disable, Drop, Enable])
    def test_is_a_single_statement(self, statement: type[Statement]) -> None:
        # ty: ignore[unknown-argument]
        assert len(split_statements(statement(pgid="p", table="orders").sql)) == 1


########################################################################################


class TestUpsertShape:
    def test_has_no_instance_dict(self) -> None:
        # slots are only real if every base declares them too
        assert not hasattr(build_upsert(), "__dict__")

    def test_is_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            build_upsert().pgid = "other"  # ty: ignore[invalid-assignment]

    def test_derived_values_are_computed_once(self) -> None:
        upsert = build_upsert()

        assert upsert.sql is upsert.sql
        assert upsert.definition is upsert.definition

    def test_equality_ignores_derived_values(self) -> None:
        assert build_upsert() == build_upsert()

    def test_equality_tracks_the_inputs(self) -> None:
        assert build_upsert() != build_upsert(func="RETURN NULL;")

    def test_repr_omits_the_sql(self) -> None:
        # otherwise a failing assertion dumps a kilobyte of PL/pgSQL
        rendered = repr(build_upsert())

        assert "pgid=" in rendered
        assert "CREATE OR REPLACE" not in rendered

    def test_str_is_the_full_script(self) -> None:
        upsert = build_upsert()

        assert str(upsert) == upsert.sql


########################################################################################


class TestUpsertRendering:
    def test_splits_into_four_statements(self) -> None:
        # ruff: ignore[magic-value-comparison]
        # # create function, drop trigger, create trigger, comment
        assert len(split_statements(build_upsert().sql)) == 4

    def test_creates_the_function_and_the_trigger(self) -> None:
        sql = build_upsert().sql

        assert "CREATE OR REPLACE FUNCTION pgtrigger_t_abcde()" in sql
        assert "CREATE TRIGGER pgtrigger_t_abcde" in sql

    def test_drops_before_creating(self) -> None:
        # a replace cannot turn a plain trigger into a constraint trigger
        sql = build_upsert().sql

        assert sql.index("DROP TRIGGER IF EXISTS") < sql.index("CREATE TRIGGER")

    def test_executes_function_not_procedure(self) -> None:
        assert "EXECUTE FUNCTION" in build_upsert().sql

    def test_consults_the_ignore_parameter(self) -> None:
        assert "CURRENT_SETTING('pgtrigger.ignore', TRUE)" in build_upsert().sql

    def test_ignore_parameter_is_configurable(self) -> None:
        upsert = build_upsert(ignore_setting="other.setting")

        assert "CURRENT_SETTING('other.setting', TRUE)" in upsert.sql

    def test_row_level_hands_a_row_back(self) -> None:
        assert "RETURN OLD; ELSE RETURN NEW;" in build_upsert().sql

    def test_statement_level_returns_null(self) -> None:
        # OLD and NEW go unassigned in a statement-level trigger
        upsert = build_upsert(for_each=ForEach.STATEMENT, time=Time.AFTER)

        assert "RETURN OLD;" not in upsert.sql.split("END IF;")[0]

    def test_constraint_trigger_says_so(self) -> None:
        upsert = build_upsert(time=Time.AFTER, execution=Execution.DEFERRED)

        assert "CREATE CONSTRAINT TRIGGER" in upsert.sql
        assert "DEFERRABLE INITIALLY DEFERRED" in upsert.sql

    def test_plain_trigger_has_no_deferrability_clause(self) -> None:
        assert "DEFERRABLE" not in build_upsert().sql

    def test_optional_clauses_are_omitted_when_empty(self) -> None:
        sql = build_upsert().sql

        assert "REFERENCING" not in sql
        assert "WHEN" not in sql
        assert "DECLARE" not in sql

    def test_optional_clauses_appear_when_given(self) -> None:
        upsert = build_upsert(
            condition="WHEN (OLD.total > 0)",
            declare="DECLARE _n INT;",
            referencing="REFERENCING OLD TABLE AS before",
            for_each=ForEach.STATEMENT,
            time=Time.AFTER,
        )

        assert "REFERENCING OLD TABLE AS before" in upsert.sql
        assert "WHEN (OLD.total > 0)" in upsert.sql
        assert "DECLARE _n INT;" in upsert.sql

    def test_rejects_a_body_that_escapes_its_quoting(self) -> None:
        with pytest.raises(ValueError, match="cannot contain"):
            build_upsert(func=f"SELECT {DOLLAR_TAG};")

    def test_rejects_a_declare_that_escapes_its_quoting(self) -> None:
        with pytest.raises(ValueError, match="cannot contain"):
            build_upsert(declare=f"DECLARE {DOLLAR_TAG}")


########################################################################################


class TestUpsertFingerprint:
    def test_definition_excludes_the_comment(self) -> None:
        # the comment carries the fingerprint, so it cannot be part of it
        assert "COMMENT ON TRIGGER" not in build_upsert().definition

    def test_sql_is_the_definition_plus_the_comment(self) -> None:
        upsert = build_upsert()

        assert upsert.sql.startswith(upsert.definition)
        assert upsert.comment in upsert.sql

    def test_is_stable(self) -> None:
        assert build_upsert().fingerprint == build_upsert().fingerprint

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("func", "RETURN NULL;"),
            ("events", "INSERT"),
            ("time", Time.AFTER),
            ("condition", "WHEN (OLD.total > 0)"),
            ("declare", "DECLARE _n INT;"),
            ("pgid", "pgtrigger_t_fffff"),
            ("table", "other"),
            ("ignore_setting", "other.setting"),
        ],
    )
    def test_every_input_changes_it(self, field: str, value: object) -> None:
        assert build_upsert().fingerprint != build_upsert(**{field: value}).fingerprint

    @ht.given(func=st.text(min_size=1).filter(lambda value: DOLLAR_TAG not in value))
    def test_any_body_produces_a_usable_fingerprint(self, func: str) -> None:
        upsert = build_upsert(func=func)

        # ruff: ignore[magic-value-comparison]
        assert len(upsert.fingerprint) == 64
        assert set(upsert.fingerprint) <= set("0123456789abcdef")


########################################################################################


class TestCompiledTrigger:
    def test_exposes_the_upsert_identity(self) -> None:
        compiled = CompiledTrigger(name="t", upsert=build_upsert())

        assert compiled.pgid == "pgtrigger_t_abcde"
        assert compiled.table == "orders"

    def test_install_sql_is_the_upsert(self) -> None:
        upsert = build_upsert()

        compiled = CompiledTrigger(name="t", upsert=upsert)

        assert compiled.install_sql == upsert.sql

    @pytest.mark.parametrize(
        ("attribute", "expected"),
        [
            ("disable_sql", "ALTER TABLE orders DISABLE TRIGGER pgtrigger_t_abcde;"),
            ("enable_sql", "ALTER TABLE orders ENABLE TRIGGER pgtrigger_t_abcde;"),
            ("uninstall_sql", "DROP TRIGGER IF EXISTS pgtrigger_t_abcde ON orders;"),
        ],
    )
    def test_derived_statements(self, attribute: str, expected: str) -> None:
        compiled = CompiledTrigger(name="t", upsert=build_upsert())

        assert getattr(compiled, attribute) == expected

    def test_is_frozen(self) -> None:
        compiled = CompiledTrigger(name="t", upsert=build_upsert())

        with pytest.raises(FrozenInstanceError):
            compiled.name = "other"  # ty: ignore[invalid-assignment]

    @ht.given(pgid=identifiers, table=identifiers)
    def test_identity_flows_through_to_every_statement(
        self,
        pgid: str,
        table: str,
    ) -> None:
        compiled = CompiledTrigger(
            name="t",
            upsert=build_upsert(pgid=pgid, table=table),
        )

        for sql in (compiled.uninstall_sql, compiled.enable_sql, compiled.disable_sql):
            assert pgid in sql
            assert table in sql
