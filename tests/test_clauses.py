"""
The clauses of a `CREATE TRIGGER` statement.
"""

from typing import TYPE_CHECKING

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.core.clauses import (
    Event,
    Events,
    Execution,
    ForEach,
    Referencing,
    UpdateOf,
)

from .builders import build_orders
from .strategies import events

if TYPE_CHECKING:
    from sqlalchemy import Table

########################################################################################


class TestForEach:
    def test_values_are_the_keywords(self) -> None:
        assert str(ForEach.ROW) == "ROW"
        assert str(ForEach.STATEMENT) == "STATEMENT"


########################################################################################


class TestExecution:
    def test_bare_value_is_what_set_constraints_expects(self) -> None:
        assert str(Execution.DEFERRED) == "DEFERRED"

    @pytest.mark.parametrize(
        ("clause", "execution"),
        [
            ("DEFERRABLE INITIALLY DEFERRED", Execution.DEFERRED),
            ("DEFERRABLE INITIALLY IMMEDIATE", Execution.IMMEDIATE),
            ("NOT DEFERRABLE", Execution.NOT_DEFERRABLE),
        ],
    )
    def test_clause_is_the_create_trigger_form(
        self,
        clause: str,
        execution: Execution,
    ) -> None:
        assert execution.clause == clause

    @pytest.mark.parametrize(
        ("deferrable", "execution"),
        [
            (True, Execution.DEFERRED),
            (True, Execution.IMMEDIATE),
            (False, Execution.NOT_DEFERRABLE),
        ],
    )
    def test_deferrable_flags_constraint_triggers(
        self,
        # ruff: ignore[boolean-type-hint-positional-argument]
        deferrable: bool,
        execution: Execution,
    ) -> None:
        assert execution.deferrable is deferrable


########################################################################################


class TestEvent:
    @ht.given(event=events)
    def test_renders_as_its_keyword(self, event: Event) -> None:
        assert event.render(build_orders()) == event.value

    @ht.given(event=events)
    def test_base_events_is_itself(self, event: Event) -> None:
        assert event.base_events == frozenset({event})

    def test_or_produces_a_group(self) -> None:
        assert isinstance(Event.INSERT | Event.UPDATE, Events)


########################################################################################


class TestEvents:
    def test_renders_joined_with_or(self, orders: Table) -> None:
        combined = Event.INSERT | Event.UPDATE

        assert combined.render(orders) == "INSERT OR UPDATE"

    def test_rejects_an_empty_group(self) -> None:
        with pytest.raises(ValueError, match="at least one event"):
            Events()

    def test_rejects_a_foreign_operand(self) -> None:
        with pytest.raises(TypeError, match="Cannot combine"):
            Event.INSERT | "DELETE"  # ty: ignore[unsupported-operator]

    @ht.given(chosen=st.lists(events, max_size=6, min_size=1))
    def test_drops_duplicates(self, chosen: list[Event]) -> None:
        combined = Events(*chosen)

        assert len(combined.events) == len(set(chosen))

    @ht.given(chosen=st.lists(events, max_size=6, min_size=1))
    def test_keeps_first_appearance_order(self, chosen: list[Event]) -> None:
        seen: list[Event] = []

        for event in chosen:
            if event not in seen:
                seen.append(event)

        assert list(Events(*chosen).events) == seen

    @ht.given(
        left=st.lists(events, max_size=3, min_size=1),
        right=st.lists(events, max_size=3, min_size=1),
    )
    def test_combining_groups_flattens_and_deduplicates(
        self, left: list[Event], right: list[Event]
    ) -> None:
        combined = Events(*left) | Events(*right)

        assert list(combined.events) == list(Events(*left, *right).events)

    @ht.given(chosen=st.lists(events, max_size=4, min_size=1))
    def test_combining_is_idempotent(self, chosen: list[Event]) -> None:
        once = Events(*chosen)

        assert once | once == once

    @ht.given(chosen=st.lists(events, max_size=4, min_size=1))
    def test_base_events_is_the_union(self, chosen: list[Event]) -> None:
        assert Events(*chosen).base_events == frozenset(chosen)

    @ht.given(chosen=st.lists(events, max_size=4, min_size=1))
    def test_equal_groups_hash_alike(self, chosen: list[Event]) -> None:
        assert hash(Events(*chosen)) == hash(Events(*chosen))

    def test_membership(self) -> None:
        assert Event.INSERT in (Event.INSERT | Event.UPDATE)
        assert Event.DELETE not in (Event.INSERT | Event.UPDATE)

    def test_iterates_its_members(self) -> None:
        assert list(Event.INSERT | Event.UPDATE) == [Event.INSERT, Event.UPDATE]


########################################################################################


class TestUpdateOf:
    def test_renders_resolved_columns(self, orders: Table) -> None:
        assert UpdateOf("status", "total").render(orders) == "UPDATE OF status, total"

    def test_quotes_where_needed(self, quoted: Table) -> None:
        assert UpdateOf("status").render(quoted) == 'UPDATE OF "Status"'

    def test_rejects_no_columns(self) -> None:
        with pytest.raises(ValueError, match="at least one column"):
            UpdateOf()

    def test_base_events_is_update(self) -> None:
        assert UpdateOf("status").base_events == frozenset({Event.UPDATE})

    def test_combines_with_a_plain_event(self, orders: Table) -> None:
        combined = Event.INSERT | UpdateOf("status")

        assert combined.render(orders) == "INSERT OR UPDATE OF status"
        assert combined.base_events == {Event.INSERT, Event.UPDATE}

    def test_equality_is_by_column_names(self) -> None:
        assert UpdateOf("a", "b") == UpdateOf("a", "b")
        assert UpdateOf("a", "b") != UpdateOf("b", "a")


########################################################################################


class TestReferencing:
    def test_renders_both_sides(self, orders: Table) -> None:
        clause = Referencing(new="after", old="before")

        assert clause.render(orders) == (
            "REFERENCING OLD TABLE AS before NEW TABLE AS after"
        )

    def test_renders_old_alone(self, orders: Table) -> None:
        assert Referencing(old="before").render(orders) == (
            "REFERENCING OLD TABLE AS before"
        )

    def test_renders_new_alone(self, orders: Table) -> None:
        assert (
            Referencing(new="after").render(orders) == "REFERENCING NEW TABLE AS after"
        )

    def test_requires_at_least_one_side(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            Referencing()

    def test_equality_and_hashing(self) -> None:
        assert Referencing(old="a") == Referencing(old="a")
        assert hash(Referencing(old="a")) == hash(Referencing(old="a"))
        assert Referencing(old="a") != Referencing(new="a")
