"""
Function body templates.
"""

from types import SimpleNamespace

import hypothesis as ht
import hypothesis.strategies as st
import pytest

from pgtrigger.core.func import Func

########################################################################################


class TestFunc:
    def test_interpolates_a_name(self) -> None:
        assert Func("SELECT {pk};").render(pk="id") == "SELECT id;"

    def test_interpolates_an_attribute(self) -> None:

        columns = SimpleNamespace(total="total")

        assert (
            Func("SELECT {columns.total};").render(columns=columns) == "SELECT total;"
        )

    def test_doubled_braces_are_literal(self) -> None:
        assert Func("{{not a placeholder}}").render() == "{not a placeholder}"

    def test_unknown_name_is_a_clear_error(self) -> None:
        with pytest.raises(ValueError, match=r"not.* available here"):
            Func("SELECT {nope};").render(pk="id")

    def test_error_lists_what_is_available(self) -> None:
        with pytest.raises(ValueError, match="pk"):
            Func("SELECT {nope};").render(pk="id")

    def test_error_mentions_brace_escaping(self) -> None:
        # a single brace in hand-written PL/pgSQL is the usual cause
        with pytest.raises(ValueError, match=r"\{\{"):
            Func("SELECT {nope};").render(pk="id")

    def test_unknown_attribute_is_a_clear_error(self) -> None:
        with pytest.raises(ValueError, match="available here"):
            Func("{columns.nope}").render(columns=SimpleNamespace(total="total"))

    @ht.given(
        body=st.text().filter(lambda value: "{" not in value and "}" not in value)
    )
    def test_a_template_without_placeholders_is_unchanged(self, body: str) -> None:
        assert Func(body).render(pk="id") == body

    def test_equality_is_by_template(self) -> None:
        assert Func("a") == Func("a")
        assert Func("a") != Func("b")
        assert Func("a") != "a"

    def test_hashes_with_equality(self) -> None:
        assert hash(Func("a")) == hash(Func("a"))

    def test_repr_is_reconstructable(self) -> None:
        assert repr(Func("a")) == "Func('a')"
