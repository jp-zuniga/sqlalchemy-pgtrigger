"""
The `WHEN` clause and the ways of building one.
"""

from typing import TYPE_CHECKING

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.core.conditions import SQL, Composite, Not, Q, coerce_condition
from pgtrigger.core.proxy import RowScope, old

from .conftest import build_orders

if TYPE_CHECKING:
    from sqlalchemy import Table

    from pgtrigger.core.conditions import Condition

########################################################################################


def resolve(condition: Condition, table: Table) -> str:
    return condition.resolve(RowScope(table=table))


########################################################################################


class TestSQL:
    def test_passes_through_unchanged(self, orders: Table) -> None:
        assert resolve(SQL("OLD.total > 0"), orders) == "OLD.total > 0"

    @pytest.mark.parametrize("value", ["", "   ", "\n"])
    def test_rejects_empty_sql(self, value: str) -> None:
        with pytest.raises(ValueError, match="Must provide SQL"):
            SQL(value)

    def test_repr_is_reconstructable(self) -> None:
        assert repr(SQL("x")) == "SQL('x')"


########################################################################################


class TestQ:
    def test_calls_the_predicate_with_old_and_new(self, orders: Table) -> None:
        condition = Q(lambda old, new: old.status != new.status)

        assert resolve(condition, orders) == "OLD.status != NEW.status"

    def test_accepts_a_prebuilt_expression(self, orders: Table) -> None:
        assert resolve(Q(old(orders).total), orders) == "OLD.total"

    def test_inlines_literals(self, orders: Table) -> None:
        # a trigger definition cannot carry bind parameters
        assert resolve(
            # ruff: ignore[unused-lambda-argument]
            Q(lambda old, new: new.status == "draft"),
            orders,
        ) == ("NEW.status = 'draft'")

    def test_rejects_a_predicate_returning_something_else(self, orders: Table) -> None:
        with pytest.raises(TypeError, match="must resolve to a SQLAlchemy expression"):
            # ruff: ignore[unused-lambda-argument]
            # ty: ignore[invalid-argument-type]
            resolve(Q(lambda old, new: "nope"), orders)

    def test_resolves_against_the_scope_it_is_given(self, orders: Table) -> None:
        # this is what makes a statement-level condition work without rewriting SQL
        scope = RowScope(table=orders, new_alias="new_values", old_alias="old_values")

        condition = Q(lambda old, new: old.total != new.total)

        assert condition.resolve(scope) == "old_values.total != new_values.total"


########################################################################################


class TestCombinators:
    def test_and_parenthesises_both_sides(self, orders: Table) -> None:
        combined = SQL("a") & SQL("b")

        assert resolve(combined, orders) == "(a) AND (b)"

    def test_or_parenthesises_both_sides(self, orders: Table) -> None:
        assert resolve(SQL("a") | SQL("b"), orders) == "(a) OR (b)"

    def test_not_wraps_its_operand(self, orders: Table) -> None:
        assert resolve(~SQL("a"), orders) == "NOT (a)"

    def test_nesting_keeps_precedence_explicit(self, orders: Table) -> None:
        combined = (SQL("a") & SQL("b")) | SQL("c")

        assert resolve(combined, orders) == "((a) AND (b)) OR (c)"

    def test_double_negation_nests_rather_than_cancelling(self, orders: Table) -> None:
        assert resolve(~~SQL("a"), orders) == "NOT (NOT (a))"

    def test_and_produces_a_composite(self) -> None:
        assert isinstance(SQL("a") & SQL("b"), Composite)

    def test_not_produces_a_not(self) -> None:
        assert isinstance(~SQL("a"), Not)

    @ht.given(count=st.integers(min_value=2, max_value=6))
    def test_chained_and_stays_balanced(self, count: int) -> None:
        table = build_orders()

        condition = SQL("x")

        for _ in range(count - 1):
            condition &= SQL("x")

        rendered = resolve(condition, table)

        assert rendered.count("(") == rendered.count(")")
        assert rendered.count("AND") == count - 1


########################################################################################


class TestCoerceCondition:
    def test_passes_none_through(self) -> None:
        assert coerce_condition(None) is None

    def test_passes_a_condition_through(self) -> None:
        condition = SQL("a")

        assert coerce_condition(condition) is condition

    def test_wraps_a_callable(self, orders: Table) -> None:
        coerced = coerce_condition(lambda old, new: old.status != new.status)

        assert isinstance(coerced, Q)
        assert resolve(coerced, orders) == "OLD.status != NEW.status"

    @pytest.mark.parametrize("value", [42, "a", object()])
    def test_rejects_anything_else(self, value: object) -> None:
        with pytest.raises(TypeError, match="Expected a Condition"):
            coerce_condition(value)  # ty: ignore[invalid-argument-type]
