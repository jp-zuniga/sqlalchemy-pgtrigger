"""
The trigger registry.
"""

import hypothesis as ht
import pytest

from sqlalchemy import Column, Integer, MetaData, Table

from pgtrigger.core.clauses import Event, Time
from pgtrigger.core.trigger import Trigger
from pgtrigger.registry import (
    add,
    clear,
    for_metadata,
    for_table,
    iterate,
    register,
    registered,
    remove,
    resolve_table,
    uris,
)
from pgtrigger.registry.entry import RegistryEntry

from .conftest import build_orders, build_scoped
from .strategies import trigger_names

########################################################################################


def build_trigger(name: str = "t") -> Trigger:
    return Trigger(
        name=name,
        time=Time.BEFORE,
        events=Event.INSERT,
        func="RETURN NEW;",
    )


########################################################################################


class TestAttachment:
    def test_table_args_registers_automatically(self) -> None:
        Table(
            "orders",
            MetaData(),
            Column("id", Integer, primary_key=True),
            build_trigger("protect"),
        )

        assert uris() == ["orders:protect"]

    def test_attach_is_idempotent(self, orders: Table) -> None:
        trigger = build_trigger()
        trigger.attach(orders)
        trigger.attach(orders)

        assert uris() == ["orders:t"]

    def test_one_trigger_serves_several_tables(self) -> None:
        trigger = build_trigger()
        trigger.attach(build_orders())
        trigger.attach(build_scoped())

        assert set(uris()) == {"orders:t", "billing.invoices:t"}

    def test_detach_removes_it(self, orders: Table) -> None:
        trigger = build_trigger()
        trigger.attach(orders)
        trigger.detach(orders)

        assert uris() == []

    def test_tables_records_attachments(self, orders: Table) -> None:
        trigger = build_trigger()
        trigger.attach(orders)

        assert trigger.tables == [orders]


########################################################################################


class TestCollisions:
    def test_duplicate_name_on_a_table_is_rejected(self, orders: Table) -> None:
        build_trigger("t").attach(orders)

        with pytest.raises(KeyError, match="already used"):
            build_trigger("t").attach(orders)

    def test_the_same_name_on_another_table_is_fine(self) -> None:
        build_trigger("t").attach(build_orders())
        build_trigger("t").attach(build_scoped())

        assert len(uris()) == 2  # ruff: ignore[magic-value-comparison]

    def test_removing_an_absent_uri_is_rejected(self) -> None:
        with pytest.raises(KeyError, match="not in the pgtrigger registry"):
            remove("orders:nope")


########################################################################################


class TestLookup:
    def test_no_arguments_returns_everything(self, orders: Table) -> None:
        build_trigger("a").attach(orders)
        build_trigger("b").attach(orders)

        assert len(registered()) == 2  # ruff: ignore[magic-value-comparison]

    def test_by_uri(self, orders: Table) -> None:
        build_trigger("a").attach(orders)
        build_trigger("b").attach(orders)

        assert [entry.uri for entry in registered("orders:a")] == ["orders:a"]

    def test_several_uris_keep_their_order(self, orders: Table) -> None:
        build_trigger("a").attach(orders)
        build_trigger("b").attach(orders)

        assert [entry.uri for entry in registered("orders:b", "orders:a")] == [
            "orders:b",
            "orders:a",
        ]

    def test_wildcard_takes_a_whole_table(self, orders: Table) -> None:
        build_trigger("a").attach(orders)
        build_trigger("b").attach(orders)
        build_trigger("c").attach(build_scoped())

        assert {entry.uri for entry in registered("orders:*")} == {
            "orders:a",
            "orders:b",
        }

    def test_wildcard_respects_the_schema(self) -> None:
        build_trigger("a").attach(build_scoped())

        assert len(registered("billing.invoices:*")) == 1

    def test_wildcard_matching_nothing_is_an_error(self) -> None:
        with pytest.raises(KeyError, match="No triggers are registered"):
            registered("ghosts:*")

    def test_unknown_uri_is_an_error(self) -> None:
        with pytest.raises(KeyError, match="not in the pgtrigger registry"):
            registered("orders:nope")

    @pytest.mark.parametrize("uri", ["orders", "a:b:c", ""])
    def test_malformed_uri_is_an_error(self, uri: str) -> None:
        with pytest.raises(ValueError, match="Malformed trigger URI"):
            registered(uri)

    def test_for_table_matches_on_identity(self) -> None:
        # two MetaData holding a table of the same name stay separate
        first, second = build_orders(), build_orders()

        build_trigger("a").attach(first)

        assert len(for_table(first)) == 1
        assert for_table(second) == []

    def test_for_metadata_confines_to_its_tables(self) -> None:
        metadata = MetaData()

        build_trigger("a").attach(build_orders(metadata))
        build_trigger("b").attach(build_orders(MetaData()))

        assert [entry.uri for entry in for_metadata(metadata)] == ["orders:a"]

    def test_iterate_walks_everything(self, orders: Table) -> None:
        build_trigger("a").attach(orders)

        assert [entry.uri for entry in iterate()] == ["orders:a"]

    def test_clear_empties_it(self, orders: Table) -> None:
        build_trigger("a").attach(orders)

        clear()

        assert uris() == []


########################################################################################


class TestRegistryEntry:
    def test_derives_the_uri(self, orders: Table) -> None:
        entry = RegistryEntry(table=orders, trigger=build_trigger("a"))

        assert entry.uri == "orders:a"
        assert str(entry) == "orders:a"

    def test_derives_the_table_uri(self, scoped: Table) -> None:
        entry = RegistryEntry(table=scoped, trigger=build_trigger("a"))

        assert entry.table_uri == "billing.invoices"

    def test_derives_the_pgid(self, orders: Table) -> None:
        trigger = build_trigger("a")
        entry = RegistryEntry(table=orders, trigger=trigger)

        assert entry.pgid == trigger.pgid(orders)

    def test_compiles(self, orders: Table) -> None:
        entry = RegistryEntry(table=orders, trigger=build_trigger("a"))

        assert entry.compile().pgid == entry.pgid


########################################################################################


class TestRegisterDecorator:
    def test_attaches_to_a_table(self, orders: Table) -> None:
        register(build_trigger("a"), build_trigger("b"))(orders)

        assert len(uris()) == 2  # ruff: ignore[magic-value-comparison]

    def test_returns_its_argument(self, orders: Table) -> None:
        assert register(build_trigger("a"))(orders) is orders

    def test_resolves_a_declarative_class(self, orders: Table) -> None:
        class Model:
            __table__ = orders

        register(build_trigger("a"))(Model)

        assert uris() == ["orders:a"]

    def test_resolve_table_passes_a_table_through(self, orders: Table) -> None:
        assert resolve_table(orders) is orders

    @pytest.mark.parametrize("value", [42, "orders", None])
    def test_resolve_table_rejects_anything_else(self, value: object) -> None:
        with pytest.raises(TypeError, match="Cannot resolve a Table"):
            resolve_table(value)


########################################################################################


class TestProperties:
    @ht.given(name=trigger_names)
    def test_a_registered_trigger_is_findable(self, name: str) -> None:
        clear()

        table = build_orders()
        trigger = build_trigger(name)
        trigger.attach(table)

        assert registered(f"orders:{name}")[0].trigger is trigger

    @ht.given(name=trigger_names)
    def test_attach_then_detach_leaves_nothing(self, name: str) -> None:
        clear()

        table = build_orders()
        trigger = build_trigger(name)
        trigger.attach(table).detach(table)

        assert uris() == []

    @ht.given(name=trigger_names)
    def test_add_is_idempotent_for_the_same_instance(self, name: str) -> None:
        clear()

        table = build_orders()
        trigger = build_trigger(name)
        uri = trigger.uri(table)

        add(uri, table=table, trigger=trigger)
        add(uri, table=table, trigger=trigger)

        assert len(uris()) == 1
