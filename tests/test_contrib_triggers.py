"""
The bundled triggers.
"""

from typing import TYPE_CHECKING

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.contrib.protect import Protect
from pgtrigger.contrib.readonly import ReadOnly
from pgtrigger.contrib.softdelete import SoftDelete
from pgtrigger.core.clauses import Event, ForEach, Time

from .conftest import build_orders
from .strategies import row_events

if TYPE_CHECKING:
    from sqlalchemy import Table

########################################################################################


class TestProtect:
    def test_defaults_to_before_at_row_level(self) -> None:
        assert Protect(name="p", events=Event.DELETE).time is Time.BEFORE

    def test_raises_in_the_body(self, orders: Table) -> None:
        sql = Protect(name="p", events=Event.DELETE).compile(orders).install_sql

        assert "RAISE EXCEPTION 'pgtrigger: cannot delete rows from % table'" in sql

    def test_message_names_every_event(self, orders: Table) -> None:
        trigger = Protect(name="p", events=Event.UPDATE | Event.DELETE)

        assert "cannot delete or update rows" in trigger.compile(orders).install_sql

    def test_forces_after_at_statement_level(self) -> None:
        # a BEFORE statement trigger fires even when no rows matched
        trigger = Protect(name="p", events=Event.DELETE, for_each=ForEach.STATEMENT)

        assert trigger.time is Time.AFTER

    @pytest.mark.parametrize(
        ("event", "expected"),
        [
            (Event.INSERT, "FROM new_values"),
            (Event.DELETE, "FROM old_values"),
            (Event.UPDATE, "FROM old_values JOIN new_values"),
        ],
    )
    def test_statement_level_tests_the_transition_tables(
        self, event: Event, expected: str
    ) -> None:
        trigger = Protect(name="p", events=event, for_each=ForEach.STATEMENT)
        sql = trigger.compile(build_orders()).install_sql

        assert expected in sql
        assert "IF EXISTS (" in sql

    def test_statement_level_applies_the_condition(self, orders: Table) -> None:
        trigger = Protect(
            name="p",
            events=Event.UPDATE,
            for_each=ForEach.STATEMENT,
            condition=lambda old, new: old.total != new.total,
        )

        assert "WHERE old_values.total != new_values.total" in (
            trigger.compile(orders).install_sql
        )

    def test_statement_level_returns_null(self, orders: Table) -> None:
        trigger = Protect(name="p", events=Event.INSERT, for_each=ForEach.STATEMENT)

        assert "RETURN NULL;" in trigger.compile(orders).install_sql

    def test_row_level_condition_becomes_a_when(self, orders: Table) -> None:
        trigger = Protect(
            name="p",
            events=Event.DELETE,
            condition=lambda old, new: old.status == "shipped",
        )

        assert "WHEN (OLD.status = 'shipped')" in trigger.compile(orders).install_sql

    @ht.given(event=row_events)
    def test_any_row_event_compiles(self, event: Event) -> None:
        trigger = Protect(name="p", events=event)

        assert event.value.lower() in trigger.compile(build_orders()).install_sql


########################################################################################


class TestReadOnly:
    def test_defaults_to_update(self) -> None:
        assert ReadOnly(name="r").events is Event.UPDATE

    def test_bare_freezes_the_whole_row(self, orders: Table) -> None:
        sql = ReadOnly(name="r").compile(orders).install_sql

        assert "OLD.* IS DISTINCT FROM NEW.*" in sql

    def test_fields_freezes_only_those(self, orders: Table) -> None:
        sql = ReadOnly(name="r", fields=["total"]).compile(orders).install_sql

        assert "OLD.total IS DISTINCT FROM NEW.total" in sql
        assert "status" not in sql.split("WHEN")[1]

    def test_exclude_freezes_everything_else(self, orders: Table) -> None:
        sql = ReadOnly(name="r", exclude=["updated_at"]).compile(orders).install_sql
        clause = sql.split("WHEN")[1]

        assert "updated_at" not in clause
        assert "total" in clause

    def test_fields_and_exclude_together_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="only one"):
            ReadOnly(name="r", exclude=["status"], fields=["total"])

    def test_an_explicit_condition_is_kept(self, orders: Table) -> None:
        # this is what lets immutability be scoped to part of a row's life
        trigger = ReadOnly(
            name="r",
            fields=["total"],
            condition=lambda old, new: old.status == "shipped",
        )
        sql = trigger.compile(orders).install_sql

        assert "IS DISTINCT FROM" in sql
        assert "OLD.status = 'shipped'" in sql
        assert " AND " in sql

    def test_raises_like_protect(self, orders: Table) -> None:
        assert "RAISE EXCEPTION" in ReadOnly(name="r").compile(orders).install_sql


########################################################################################


class TestSoftDelete:
    def test_defaults(self) -> None:
        trigger = SoftDelete(name="s", field="status")

        assert trigger.time is Time.BEFORE
        assert trigger.events is Event.DELETE

    def test_requires_a_field(self) -> None:
        with pytest.raises(ValueError, match='Must provide "field"'):
            SoftDelete(name="s")

    def test_updates_and_cancels_the_delete(self, orders: Table) -> None:
        sql = SoftDelete(name="s", field="status").compile(orders).install_sql

        assert "UPDATE orders" in sql
        assert "WHERE id = OLD.id" in sql
        assert "RETURN NULL;" in sql

    @pytest.mark.parametrize(
        ("value", "rendered"),
        [
            (False, "FALSE"),
            (True, "TRUE"),
            (None, "NULL"),
            (0, "0"),
            (7, "7"),
            ("gone", "'gone'"),
            ("it's", "'it''s'"),
        ],
    )
    def test_renders_the_marker_value(
        self,
        # ruff: ignore[boolean-type-hint-positional-argument]
        value: bool | int | str | None,
        rendered: str,
    ) -> None:
        trigger = SoftDelete(name="s", field="status", value=value)

        assert f"SET status = {rendered}" in trigger.compile(build_orders()).install_sql

    def test_default_value_is_false(self, orders: Table) -> None:
        # the sentinel default has to be distinguishable from an explicit None
        assert "SET status = FALSE" in (
            SoftDelete(name="s", field="status").compile(orders).install_sql
        )

    def test_composite_primary_key(self, composite: Table) -> None:
        trigger = SoftDelete(name="s", field="delivered", value=True)
        sql = trigger.compile(composite).install_sql

        assert "WHERE (order_id, leg) = (OLD.order_id, OLD.leg)" in sql

    def test_quotes_the_marker_column(self, quoted: Table) -> None:
        trigger = SoftDelete(name="s", field="status", value="gone")

        assert 'SET "Status" = ' in trigger.compile(quoted).install_sql

    @ht.given(value=st.integers())
    def test_any_integer_marker_renders(self, value: int) -> None:
        trigger = SoftDelete(name="s", field="total", value=value)

        assert f"SET total = {value}" in trigger.compile(build_orders()).install_sql

    @ht.given(
        value=st.text(max_size=40).filter(
            # the body is normalised line by line, so a marker containing any
            # line boundary would not appear contiguously in the output
            lambda text: "$pgtrigger$" not in text and text.splitlines() in ([text], [])
        )
    )
    def test_any_string_marker_is_escaped(self, value: str) -> None:
        trigger = SoftDelete(name="s", field="status", value=value)
        expected = "'" + value.replace("'", "''") + "'"

        assert f"SET status = {expected}" in trigger.compile(build_orders()).install_sql
