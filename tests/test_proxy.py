"""
Row proxies and the scope a condition resolves in.
"""

from typing import TYPE_CHECKING

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.core.clauses import Referencing
from pgtrigger.core.proxy import RowScope, new, old
from pgtrigger.enums import TransitionTable
from pgtrigger.utils.sql import compile_expression

from .conftest import build_orders

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import Table

    from pgtrigger.core import RowProxy

########################################################################################


class TestRowProxy:
    def test_renders_the_alias_unquoted(self, orders: Table) -> None:
        # PostgreSQL rejects "OLD"."status" in a trigger condition
        assert compile_expression(old(orders).status) == "OLD.status"

    def test_quotes_the_column_where_needed(self, quoted: Table) -> None:
        assert compile_expression(old(quoted).status) == 'OLD."Status"'

    def test_attribute_and_item_access_agree(self, orders: Table) -> None:
        proxy = old(orders)

        assert proxy.status is proxy["status"]

    def test_c_and_columns_are_the_same_collection(self, orders: Table) -> None:
        proxy = old(orders)

        assert proxy.c is proxy.columns

    def test_resolves_by_database_name_too(self, quoted: Table) -> None:
        assert compile_expression(old(quoted)["Status"]) == 'OLD."Status"'

    def test_unknown_column_raises_attribute_error(self, orders: Table) -> None:
        with pytest.raises(AttributeError, match="not a column"):
            _ = old(orders).nope

    def test_unknown_column_lists_what_is_available(self, orders: Table) -> None:
        with pytest.raises(AttributeError, match="total"):
            _ = old(orders).nope

    def test_dunder_lookups_are_not_columns(self, orders: Table) -> None:
        # otherwise copy, pickle and inspect all misbehave
        with pytest.raises(AttributeError):
            _ = old(orders).__deepcopy__

    def test_whole_row_reference(self, orders: Table) -> None:
        assert compile_expression(old(orders).all) == "OLD.*"

    def test_repr_names_the_alias_and_table(self, orders: Table) -> None:
        assert repr(new(orders)) == "<NEW orders>"

    @pytest.mark.parametrize(
        ("factory", "alias"),
        [(new, TransitionTable.NEW), (old, TransitionTable.OLD)],
    )
    def test_helpers_pick_the_right_alias(
        self,
        factory: Callable[[Table], RowProxy],
        alias: TransitionTable,
    ) -> None:
        assert factory(build_orders()).alias == alias


########################################################################################


class TestRowScope:
    def test_defaults_to_old_and_new(self, orders: Table) -> None:
        scope = RowScope(table=orders)

        assert scope.old.alias == "OLD"
        assert scope.new.alias == "NEW"

    def test_transitions_take_the_referencing_names(self, orders: Table) -> None:
        scope = RowScope.transitions(Referencing(new="after", old="before"), orders)

        assert scope.old.alias == "before"
        assert scope.new.alias == "after"

    def test_absent_side_falls_back(self, orders: Table) -> None:
        # a DELETE trigger has no NEW table; referencing it is caught by validation
        scope = RowScope.transitions(Referencing(old="before"), orders)

        assert scope.old.alias == "before"
        assert scope.new.alias == "NEW"

    def test_renders_against_the_transition_tables(self, orders: Table) -> None:
        scope = RowScope.transitions(Referencing(new="after", old="before"), orders)

        assert compile_expression(scope.old.total) == "before.total"
        assert compile_expression(scope.new.total) == "after.total"

    def test_is_frozen(self, orders: Table) -> None:
        scope = RowScope(table=orders)

        with pytest.raises(AttributeError):
            scope.table = orders  # ty: ignore[invalid-assignment]

    @ht.given(
        new_alias=st.from_regex(r"\A[a-z][a-z0-9_]{0,12}\Z"),
        old_alias=st.from_regex(r"\A[a-z][a-z0-9_]{0,12}\Z"),
    )
    def test_any_alias_prefixes_the_column(
        self,
        old_alias: str,
        new_alias: str,
    ) -> None:
        table = build_orders()
        scope = RowScope(table=table, new_alias=new_alias, old_alias=old_alias)

        assert compile_expression(scope.old.total) == f"{old_alias}.total"
        assert compile_expression(scope.new.total) == f"{new_alias}.total"
