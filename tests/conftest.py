"""
Shared fixtures and test-wide setup.
"""

from typing import TYPE_CHECKING

import pytest

from hypothesis import HealthCheck, settings

from pgtrigger.registry import clear

from .builders import build_composite, build_orders, build_quoted, build_scoped

if TYPE_CHECKING:
    from sqlalchemy import Table

########################################################################################

settings.register_profile(
    "default",
    deadline=None,
    suppress_health_check=(HealthCheck.function_scoped_fixture,),
)

settings.load_profile("default")

########################################################################################


def pytest_runtest_setup() -> None:
    """
    Empty the trigger registry before each test.

    The registry is process-global, so without this a name declared in one test
    collides with the same name in the next and the failure lands nowhere near
    its cause.

    A hook rather than an autouse fixture;
    hypothesis treats a function-scoped
    fixture on a `@given` test as a health-check failure,
    and this one resets global state rather than producing test data.
    """

    clear()


def pytest_runtest_teardown() -> None:
    """
    Empty the trigger registry after each test, so nothing leaks into the next.
    """

    clear()


########################################################################################


@pytest.fixture
def composite() -> Table:
    """
    Provide a table with a composite primary key.

    Returns:
        Table: See `tests.builders.build_composite`.

    """

    return build_composite()


@pytest.fixture
def orders() -> Table:
    """
    Provide the standard table.

    Returns:
        Table: See `tests.builders.build_orders`.

    """

    return build_orders()


@pytest.fixture
def scoped() -> Table:
    """
    Provide a schema-qualified table.

    Returns:
        Table: See `tests.builders.build_scoped`.

    """

    return build_scoped()


@pytest.fixture
def quoted() -> Table:
    """
    Provide a table whose names need quoting.

    Returns:
        Table: See `tests.builders.build_quoted`.

    """

    return build_quoted()
