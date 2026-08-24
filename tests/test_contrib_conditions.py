"""
Change-detection conditions.
"""

from typing import TYPE_CHECKING, Final

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.contrib.conditions import (
    AllChange,
    AllDontChange,
    AnyChange,
    AnyDontChange,
)
from pgtrigger.core.proxy import RowScope

from .conftest import build_orders

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Table

    from pgtrigger.core.conditions import Condition

########################################################################################

COLUMNS: Final[Sequence[str]] = ("id", "status", "total", "updated_at")

########################################################################################


def resolve(condition: Condition, table: Table) -> str:
    return condition.resolve(RowScope(table=table))


########################################################################################


class TestWholeRowShortcut:
    def test_any_change_with_no_fields(self, orders: Table) -> None:
        assert resolve(AnyChange(), orders) == "OLD.* IS DISTINCT FROM NEW.*"

    def test_any_dont_change_with_no_fields(self, orders: Table) -> None:
        assert resolve(AnyDontChange(), orders) == "OLD.* IS NOT DISTINCT FROM NEW.*"

    def test_naming_every_column_is_the_same_as_naming_none(
        self,
        orders: Table,
    ) -> None:
        assert resolve(AnyChange(*COLUMNS), orders) == resolve(AnyChange(), orders)

    def test_all_change_does_not_take_the_shortcut(self, orders: Table) -> None:
        # "every column changed" is not "the row changed"
        assert resolve(AllChange(), orders) != "OLD.* IS DISTINCT FROM NEW.*"


########################################################################################


class TestFieldSelection:
    def test_named_fields_only(self, orders: Table) -> None:
        assert resolve(AnyChange("total"), orders) == (
            "OLD.total IS DISTINCT FROM NEW.total"
        )

    def test_fields_are_sorted_for_stability(self, orders: Table) -> None:
        # the same declaration has to fingerprint the same way every run
        assert resolve(AnyChange("total", "status"), orders) == resolve(
            AnyChange("status", "total"),
            orders,
        )

    def test_exclude_removes_a_column(self, orders: Table) -> None:
        rendered = resolve(AnyChange(exclude=["updated_at"]), orders)

        assert "updated_at" not in rendered
        assert "total" in rendered

    def test_exclude_auto_drops_onupdate_columns(self, orders: Table) -> None:
        rendered = resolve(AnyChange(exclude_auto=True), orders)

        assert "updated_at" not in rendered

    def test_exclude_auto_keeps_everything_else(self, orders: Table) -> None:
        rendered = resolve(AnyChange(exclude_auto=True), orders)

        assert "status" in rendered
        assert "total" in rendered

    def test_excluding_everything_is_an_error(self, orders: Table) -> None:
        with pytest.raises(ValueError, match="No fields remain"):
            resolve(AnyChange(exclude=COLUMNS), orders)

    def test_unknown_field_is_an_error(self, orders: Table) -> None:
        with pytest.raises(ValueError, match="does not resolve"):
            resolve(AnyChange("nope"), orders)


########################################################################################


class TestOperators:
    def test_any_joins_with_or(self, orders: Table) -> None:
        assert " OR " in resolve(AnyChange("status", "total"), orders)

    def test_all_joins_with_and(self, orders: Table) -> None:
        assert " AND " in resolve(AllChange("status", "total"), orders)

    def test_change_uses_is_distinct_from(self, orders: Table) -> None:
        assert "IS DISTINCT FROM" in resolve(AnyChange("total"), orders)

    def test_dont_change_uses_is_not_distinct_from(self, orders: Table) -> None:
        assert "IS NOT DISTINCT FROM" in resolve(AnyDontChange("total"), orders)

    def test_all_dont_change_joins_with_and(self, orders: Table) -> None:
        rendered = resolve(AllDontChange("status", "total"), orders)

        assert " AND " in rendered
        assert "IS NOT DISTINCT FROM" in rendered


########################################################################################


class TestNegation:
    def test_wraps_in_not(self, orders: Table) -> None:
        assert resolve(~AnyChange("total"), orders).startswith("NOT (")

    def test_leaves_the_original_alone(self, orders: Table) -> None:
        condition = AnyChange("total")

        _ = ~condition

        assert not resolve(condition, orders).startswith("NOT (")

    def test_double_negation_cancels(self, orders: Table) -> None:
        # unlike Not(), which nests, inverting a Change toggles a flag
        assert resolve(~~AnyChange("total"), orders) == resolve(
            AnyChange("total"),
            orders,
        )


########################################################################################


class TestProperties:
    @ht.given(
        fields=st.lists(
            elements=st.sampled_from(COLUMNS),
            max_size=3,
            min_size=1,
            unique=True,
        )
    )
    def test_every_named_field_appears(self, fields: list[str]) -> None:
        # a proper subset, so the whole-row shortcut does not apply
        table = build_orders()
        rendered = resolve(AnyChange(*fields), table)

        assert all(field in rendered for field in fields)

    @ht.given(
        fields=st.lists(
            elements=st.sampled_from(COLUMNS),
            max_size=4,
            min_size=1,
            unique=True,
        )
    )
    def test_field_order_does_not_change_the_sql(self, fields: list[str]) -> None:
        table = build_orders()

        assert resolve(AnyChange(*fields), table) == resolve(
            AnyChange(*reversed(fields)), table
        )

    @ht.given(
        fields=st.lists(
            elements=st.sampled_from(COLUMNS),
            max_size=3,
            min_size=2,
            unique=True,
        )
    )
    def test_comparison_count_matches_field_count(self, fields: list[str]) -> None:
        table = build_orders()
        rendered = resolve(AnyChange(*fields), table)

        assert rendered.count("IS DISTINCT FROM") == len(fields)

    @ht.given(excluded=st.lists(st.sampled_from(COLUMNS), max_size=3, unique=True))
    def test_excluded_fields_never_appear(self, excluded: list[str]) -> None:
        table = build_orders()

        if len(excluded) == len(COLUMNS):
            return

        rendered = resolve(AnyChange(exclude=excluded), table)

        if rendered == "OLD.* IS DISTINCT FROM NEW.*":
            assert not excluded
        else:
            assert all(field not in rendered for field in excluded)
