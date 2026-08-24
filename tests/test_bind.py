"""
Rejecting connectables that cannot do the job.
"""

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from sqlalchemy import create_engine

from pgtrigger.core.clauses import Event, Time
from pgtrigger.core.trigger import Trigger
from pgtrigger.installation.bind import bind
from pgtrigger.runtime.settings import parse_array, pgids, render_array, require_scoped

from .builders import build_orders
from .strategies import identifiers

########################################################################################


class TestBind:
    @pytest.mark.parametrize(
        "value",
        [
            42,
            "engine",
            None,
            object(),
        ],
    )
    def test_rejects_what_cannot_run_sql(self, value: object) -> None:
        # ty: ignore[invalid-argument-type]
        with pytest.raises(TypeError, match="Expected an Engine"), bind(value):
            pass

    def test_accepts_anything_with_execute(self) -> None:
        class Fake:
            def execute(self, *args: object, **kwargs: object) -> None:
                pass

        fake = Fake()

        with bind(fake) as executor:  # ty: ignore[invalid-argument-type]
            assert executor is fake


########################################################################################


class TestRequireScoped:
    def test_rejects_an_engine(self) -> None:
        engine = create_engine("postgresql+psycopg://localhost/x")

        with pytest.raises(TypeError, match="not an Engine"):
            require_scoped(engine, "ignore")

    @pytest.mark.parametrize("value", [42, None, object()])
    def test_rejects_what_cannot_run_sql(self, value: object) -> None:
        with pytest.raises(TypeError, match="expected a Connection or Session"):
            require_scoped(value, "ignore")  # ty: ignore[invalid-argument-type]

    def test_names_the_caller_in_the_message(self) -> None:
        with pytest.raises(TypeError, match="ignored"):
            require_scoped(42, "ignored")  # ty: ignore[invalid-argument-type]


########################################################################################


class TestArrayEncoding:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, []),
            ("", []),
            ("{}", []),
            ("{a}", ["a"]),
            ("{a,b}", ["a", "b"]),
        ],
    )
    def test_parses_postgres_array_literals(
        self,
        value: str | None,
        expected: list[str],
    ) -> None:
        assert parse_array(value) == expected

    def test_renders_an_empty_array(self) -> None:
        assert render_array([]) == "{}"

    def test_sorts_and_deduplicates(self) -> None:
        assert render_array(["b", "a", "b"]) == "{a,b}"

    @ht.given(values=st.lists(identifiers, max_size=6))
    def test_round_trips(self, values: list[str]) -> None:
        assert parse_array(render_array(values)) == sorted(set(values))

    @ht.given(values=st.lists(identifiers, max_size=6))
    def test_rendering_is_idempotent(self, values: list[str]) -> None:
        once = render_array(values)

        assert render_array(parse_array(once)) == once


########################################################################################


class TestPgids:
    def test_resolves_registered_triggers(self) -> None:
        table = build_orders()

        trigger = Trigger(
            name="t",
            time=Time.BEFORE,
            events=Event.INSERT,
            func="RETURN NEW;",
        )

        trigger.attach(table)

        assert pgids("orders:t") == [trigger.pgid(table)]

    def test_unknown_uri_is_an_error(self) -> None:
        with pytest.raises(KeyError):
            pgids("orders:nope")
