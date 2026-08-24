"""
Declaring a trigger: defaults, validation, and rendering.
"""

from typing import TYPE_CHECKING, Unpack

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.consts import MAX_NAME_LENGTH, MAX_PGID_LENGTH, PGID_PREFIX
from pgtrigger.core.clauses import Event, Execution, ForEach, Referencing, Time
from pgtrigger.core.conditions import SQL, Q
from pgtrigger.core.func import Func
from pgtrigger.core.trigger import Trigger
from pgtrigger.utils.sql import dedent_sql

from .conftest import build_orders, build_scoped
from .strategies import invalid_names, row_events, trigger_names

if TYPE_CHECKING:
    from sqlalchemy import Table

    from pgtrigger.core import TriggerKwargs

########################################################################################


def minimal(**kwargs: Unpack[TriggerKwargs]) -> Trigger:
    # ty: ignore[invalid-argument-type]
    return Trigger(**{
        "name": "t",
        "time": Time.BEFORE,
        "events": Event.INSERT,
        "func": "RETURN NEW;",
        **kwargs,
    })


########################################################################################


class TestDefaults:
    def test_optional_clauses_default_to_none(self) -> None:
        trigger = minimal()

        assert trigger.execution is None
        assert trigger.referencing is None
        assert trigger.condition is None
        assert trigger.declare is None

    def test_for_each_defaults_to_row(self) -> None:
        assert minimal().for_each is ForEach.ROW

    def test_subclass_class_attributes_survive(self) -> None:
        class Audited(Trigger):
            time = Time.AFTER
            events = Event.UPDATE
            func = "RETURN NULL;"

        trigger = Audited(name="audited")

        assert trigger.time is Time.AFTER
        assert trigger.events is Event.UPDATE

    def test_subclass_defaults_inherit_through_two_levels(self) -> None:
        class Audited(Trigger):
            time = Time.AFTER
            events = Event.INSERT
            func = "RETURN NULL;"

        class Bulk(Audited):
            for_each = ForEach.STATEMENT

        trigger = Bulk(name="bulk")

        assert trigger.time is Time.AFTER
        assert trigger.for_each is ForEach.STATEMENT

    def test_an_argument_beats_a_subclass_default(self) -> None:
        class Audited(Trigger):
            time = Time.AFTER
            events = Event.INSERT
            func = "RETURN NULL;"

        assert Audited(name="a", time=Time.BEFORE).time is Time.BEFORE

    def test_omitting_for_each_does_not_clobber_a_subclass_default(self) -> None:
        # the signature default has to be None, not ForEach.ROW
        class Bulk(Trigger):
            time = Time.AFTER
            events = Event.INSERT
            for_each = ForEach.STATEMENT
            func = "RETURN NULL;"

        assert Bulk(name="b").for_each is ForEach.STATEMENT

    def test_a_callable_condition_is_wrapped(self) -> None:
        # ruff: ignore[unused-lambda-argument]
        trigger = minimal(condition=lambda old, new: new.total > 0)

        assert isinstance(trigger.condition, Q)


########################################################################################


class TestRequired:
    @pytest.mark.parametrize("missing", ["name", "time", "events"])
    def test_each_is_reported_by_name(self, missing: str) -> None:
        kwargs: TriggerKwargs = {
            "name": "t",
            "time": Time.BEFORE,
            "events": Event.INSERT,
            "func": "RETURN NEW;",
        }

        del kwargs[missing]  # ty: ignore[invalid-argument-type]

        with pytest.raises(ValueError, match=f'Must provide "{missing}"'):
            Trigger(**kwargs)


########################################################################################


class TestNameValidation:
    @ht.given(name=trigger_names)
    def test_accepts_anything_matching_the_documented_pattern(self, name: str) -> None:
        assert minimal(name=name).name == name

    @ht.given(name=invalid_names)
    def test_rejects_characters_outside_the_pattern(self, name: str) -> None:
        with pytest.raises(ValueError, match=r"invalid characters|characters;"):
            minimal(name=name)

    @pytest.mark.parametrize("name", ["abc\n", "abc\r\n", "\nabc"])
    def test_rejects_a_name_with_a_line_break(self, name: str) -> None:
        # `$` in a pattern also matches before a trailing newline,
        # which would put one into the generated identifier
        with pytest.raises(ValueError, match="invalid characters"):
            minimal(name=name)

    def test_rejects_a_name_over_the_limit(self) -> None:
        with pytest.raises(ValueError, match="maximum"):
            minimal(name="a" * (MAX_NAME_LENGTH + 1))

    def test_accepts_a_name_at_the_limit(self) -> None:
        assert minimal(name="a" * MAX_NAME_LENGTH)

    @ht.given(name=trigger_names)
    def test_pgid_fits_a_postgres_identifier(self, name: str) -> None:
        table = build_orders()

        assert len(minimal(name=name).pgid(table)) <= MAX_PGID_LENGTH

    @ht.given(name=trigger_names)
    def test_pgid_is_lowercase_and_prefixed(self, name: str) -> None:
        # PostgreSQL folds unquoted identifiers, so lookups must match
        pgid = minimal(name=name).pgid(build_orders())

        assert pgid == pgid.lower()
        assert pgid.startswith(PGID_PREFIX)

    @ht.given(name=trigger_names)
    def test_pgid_is_stable(self, name: str) -> None:
        table = build_orders()

        assert minimal(name=name).pgid(table) == minimal(name=name).pgid(table)

    def test_pgid_differs_across_tables(self) -> None:
        trigger = minimal()

        assert trigger.pgid(build_orders()) != trigger.pgid(build_scoped())


########################################################################################


class TestUri:
    def test_unqualified_table(self, orders: Table) -> None:
        assert minimal(name="protect").uri(orders) == "orders:protect"

    def test_qualified_table(self, scoped: Table) -> None:
        assert minimal(name="protect").uri(scoped) == "billing.invoices:protect"


########################################################################################


class TestValidation:
    def test_truncate_must_be_statement_level(self) -> None:
        with pytest.raises(ValueError, match=r"ForEach\.STATEMENT"):
            minimal(time=Time.AFTER, events=Event.TRUNCATE)

    def test_truncate_cannot_have_a_condition(self) -> None:
        with pytest.raises(ValueError, match="cannot have a condition"):
            minimal(
                time=Time.AFTER,
                events=Event.TRUNCATE,
                for_each=ForEach.STATEMENT,
                condition=SQL("x"),
            )

    def test_referencing_needs_statement_level(self) -> None:
        with pytest.raises(ValueError, match="statement-level"):
            minimal(time=Time.AFTER, referencing=Referencing(new="n"))

    def test_referencing_needs_after(self) -> None:
        with pytest.raises(ValueError, match=r"Time\.AFTER"):
            minimal(
                time=Time.BEFORE,
                for_each=ForEach.STATEMENT,
                referencing=Referencing(new="n"),
            )

    def test_referencing_needs_a_single_event(self) -> None:
        with pytest.raises(ValueError, match="single event"):
            minimal(
                time=Time.AFTER,
                events=Event.INSERT | Event.UPDATE,
                for_each=ForEach.STATEMENT,
                referencing=Referencing(new="n"),
            )

    def test_statement_condition_needs_transition_tables(self) -> None:
        with pytest.raises(ValueError, match="transition tables"):
            minimal(
                time=Time.AFTER,
                events=Event.INSERT | Event.UPDATE,
                for_each=ForEach.STATEMENT,
                condition=SQL("x"),
            )

    def test_deferrable_needs_after(self) -> None:
        with pytest.raises(ValueError, match=r"Time\.AFTER"):
            minimal(time=Time.BEFORE, execution=Execution.DEFERRED)

    def test_deferrable_needs_row_level(self) -> None:
        with pytest.raises(ValueError, match="row-level"):
            minimal(
                time=Time.AFTER,
                for_each=ForEach.STATEMENT,
                execution=Execution.DEFERRED,
            )

    def test_not_deferrable_is_exempt(self) -> None:
        assert minimal(time=Time.BEFORE, execution=Execution.NOT_DEFERRABLE)

    def test_instead_of_needs_row_level(self) -> None:
        with pytest.raises(ValueError, match="row-level"):
            minimal(time=Time.INSTEAD_OF, for_each=ForEach.STATEMENT)

    def test_instead_of_cannot_have_a_condition(self) -> None:
        with pytest.raises(ValueError, match="cannot have a condition"):
            minimal(time=Time.INSTEAD_OF, condition=SQL("x"))

    @pytest.mark.parametrize(
        ("expected", "field", "value"),
        [
            (TypeError, "time", "BEFORE"),
            (TypeError, "for_each", "ROW"),
            (ValueError, "execution", "DEFERRED"),
        ],
    )
    def test_rejects_a_raw_string_where_an_enum_belongs(
        self,
        expected: type[Exception],
        field: str,
        value: str,
    ) -> None:
        with pytest.raises(expected, match="Invalid"):
            minimal(**{field: value})  # ty: ignore[invalid-argument-type]


########################################################################################


class TestReferencingDerivation:
    @pytest.mark.parametrize(
        ("event", "has_old", "has_new"),
        [
            (Event.INSERT, False, True),
            (Event.UPDATE, True, True),
            (Event.DELETE, True, False),
        ],
    )
    def test_single_event_gets_the_sides_it_has(
        self,
        event: Event,
        has_old: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
        has_new: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
    ) -> None:
        trigger = minimal(time=Time.AFTER, events=event, for_each=ForEach.STATEMENT)

        assert trigger.referencing is not None
        assert bool(trigger.referencing.old) is has_old
        assert bool(trigger.referencing.new) is has_new

    def test_multiple_events_get_none(self) -> None:
        trigger = minimal(
            time=Time.AFTER,
            events=Event.INSERT | Event.UPDATE,
            for_each=ForEach.STATEMENT,
        )

        assert trigger.referencing is None

    def test_before_gets_none(self) -> None:
        # transition tables are only populated once the statement has run
        trigger = minimal(
            time=Time.BEFORE, events=Event.INSERT, for_each=ForEach.STATEMENT
        )

        assert trigger.referencing is None

    def test_row_level_gets_none(self) -> None:
        assert minimal(time=Time.AFTER, events=Event.INSERT).referencing is None

    def test_an_explicit_clause_is_kept(self) -> None:
        explicit = Referencing(new="after")
        trigger = minimal(
            time=Time.AFTER,
            events=Event.INSERT,
            for_each=ForEach.STATEMENT,
            referencing=explicit,
        )

        assert trigger.referencing is explicit


########################################################################################


class TestRendering:
    def test_condition_is_fully_parenthesised(self, orders: Table) -> None:
        # PostgreSQL wants WHEN ( condition ); "(a) AND (b)" is not that
        trigger = minimal(condition=SQL("a") & SQL("b"))

        assert trigger.render_condition(orders) == "WHEN ((a) AND (b))"

    def test_no_condition_renders_empty(self, orders: Table) -> None:
        # ruff: ignore[compare-to-empty-string]
        assert minimal().render_condition(orders) == ""

    def test_statement_level_never_renders_a_when(self, orders: Table) -> None:
        trigger = minimal(
            time=Time.AFTER,
            events=Event.INSERT,
            for_each=ForEach.STATEMENT,
            condition=SQL("a"),
            func="RETURN NULL;",
        )

        # ruff: ignore[compare-to-empty-string]
        assert trigger.render_condition(orders) == ""

    def test_statement_level_condition_becomes_a_where(self, orders: Table) -> None:
        trigger = minimal(
            time=Time.AFTER,
            events=Event.INSERT,
            for_each=ForEach.STATEMENT,
            condition=SQL("a"),
            func="RETURN NULL;",
        )

        assert trigger.render_where(orders) == "WHERE a"

    def test_declare_renders_each_variable(self, orders: Table) -> None:
        trigger = minimal(declare=[("_row", "JSONB"), ("_n", "INT")])

        assert trigger.render_declare(orders) == "DECLARE _row JSONB; _n INT;"

    def test_no_declare_renders_empty(self, orders: Table) -> None:
        # ruff: ignore[compare-to-empty-string]
        assert minimal().render_declare(orders) == ""

    def test_func_is_normalised_to_column_zero(self, orders: Table) -> None:
        trigger = minimal(func="\n    SELECT 1;\n    RETURN NEW;\n")

        assert trigger.render_func(orders) == "SELECT 1;\nRETURN NEW;"


########################################################################################


class TestFuncContext:
    def test_columns_are_quoted_where_needed(self, quoted: Table) -> None:
        trigger = minimal(func=Func("SELECT {columns.status};"))

        assert trigger.render_func(quoted) == 'SELECT "Status";'

    def test_names_are_raw(self, quoted: Table) -> None:
        trigger = minimal(func=Func("SELECT {names.status};"))

        assert trigger.render_func(quoted) == "SELECT Status;"

    def test_pk_lists_the_primary_key(self, composite: Table) -> None:
        trigger = minimal(func=Func("SELECT {pk};"))

        assert trigger.render_func(composite) == "SELECT order_id, leg;"

    def test_statement_level_gets_transition_names(self, orders: Table) -> None:
        trigger = minimal(
            time=Time.AFTER,
            events=Event.UPDATE,
            for_each=ForEach.STATEMENT,
            func=Func("SELECT 1 FROM {changed_rows} {where}; RETURN NULL;"),
        )

        assert "old_values JOIN new_values" in trigger.render_func(orders)

    def test_row_level_does_not(self, orders: Table) -> None:
        trigger = minimal(func=Func("SELECT {new_rows};"))

        with pytest.raises(ValueError, match="available here"):
            trigger.render_func(orders)

    def test_absent_side_is_not_offered(self, orders: Table) -> None:
        # a DELETE statement trigger has no NEW table
        trigger = minimal(
            time=Time.AFTER,
            events=Event.DELETE,
            for_each=ForEach.STATEMENT,
            func=Func("SELECT {new_rows};"),
        )

        with pytest.raises(ValueError, match="available here"):
            trigger.render_func(orders)

    def test_where_is_empty_without_a_condition(self, orders: Table) -> None:
        trigger = minimal(
            time=Time.AFTER,
            events=Event.INSERT,
            for_each=ForEach.STATEMENT,
            func=Func("SELECT 1 FROM {new_rows} {where};"),
        )

        assert trigger.render_func(orders) == "SELECT 1 FROM new_values ;"


########################################################################################


class TestGetFunc:
    def test_missing_func_is_a_clear_error(self, orders: Table) -> None:
        trigger = Trigger(name="t", time=Time.BEFORE, events=Event.INSERT)

        with pytest.raises(ValueError, match="no function"):
            trigger.get_func(orders)

    def test_a_mapping_selects_by_level(self, orders: Table) -> None:
        bodies = {ForEach.ROW: "RETURN NEW;", ForEach.STATEMENT: "RETURN NULL;"}

        assert minimal(func=bodies).get_func(orders) == "RETURN NEW;"

    def test_a_mapping_missing_this_level_is_an_error(self, orders: Table) -> None:
        trigger = minimal(
            time=Time.AFTER,
            events=Event.INSERT,
            for_each=ForEach.STATEMENT,
            func={ForEach.ROW: "RETURN NEW;"},
        )

        with pytest.raises(ValueError, match="no function for"):
            trigger.get_func(orders)


########################################################################################


class TestProperties:
    @ht.given(name=trigger_names, event=row_events)
    def test_any_valid_row_trigger_compiles(self, name: str, event: Event) -> None:
        table = build_orders()
        compiled = minimal(name=name, events=event).compile(table)

        assert compiled.pgid in compiled.install_sql
        assert compiled.fingerprint

    @ht.given(name=trigger_names, event=row_events)
    def test_compiling_twice_agrees(self, name: str, event: Event) -> None:
        table = build_orders()

        assert (
            minimal(name=name, events=event).compile(table).fingerprint
            == minimal(name=name, events=event).compile(table).fingerprint
        )

    @ht.given(left=row_events, right=row_events)
    def test_different_events_fingerprint_differently(
        self, left: Event, right: Event
    ) -> None:
        table = build_orders()

        if left is right:
            return

        assert (
            minimal(events=left).compile(table).fingerprint
            != minimal(events=right).compile(table).fingerprint
        )

    @ht.given(body=st.text(min_size=1).filter(lambda value: "$pgtrigger$" not in value))
    def test_the_body_reaches_the_generated_function(self, body: str) -> None:
        table = build_orders()
        rendered = minimal(func=body).compile(table).install_sql
        normalised = dedent_sql(body)

        if normalised:
            assert normalised.splitlines()[0].strip() in rendered
