"""
Refusing an operation outright.
"""

from typing import TYPE_CHECKING, override

from pgtrigger.core import ForEach, Func, Time, Trigger, TriggerKwargs

if TYPE_CHECKING:
    from typing import Unpack

    from sqlalchemy import Table

########################################################################################


class Protect(Trigger):
    """
    Refuses an operation outright.

    ```python
    pgtrigger.Protect(events=pgtrigger.Event.DELETE, name="no_deletes")
    ```

    Add a condition to protect only some rows:

    ```python
    pgtrigger.Protect(
        condition=(lambda old, new: old.status == "shipped"),
        events=pgtrigger.Event.DELETE,
        name="no_shipped_deletes",
    )
    ```

    The exception surfaces as a `DBAPIError` whose message begins `pgtrigger:`,
    which is enough to tell it apart from a constraint violation when turning it
    into an HTTP response.
    """

    @override
    def __init__(self, **kwargs: Unpack[TriggerKwargs]) -> None:
        kwargs.setdefault("time", Time.BEFORE)

        super().__init__(**kwargs)

    @override
    def _configure(self) -> None:
        """
        Force `AFTER` at statement level.

        A `BEFORE` statement-level trigger fires even when the statement matches
        no rows, so an unconditional one would reject `DELETE ... WHERE false`.
        Firing afterwards and testing the transition table is the honest check,
        and it is also the only way a condition can be evaluated at all.
        """

        if self.for_each is ForEach.STATEMENT:
            self.time = Time.AFTER

        super()._configure()

    @override
    def get_func(self, table: Table) -> str | Func:
        """
        Raise, either per row or once for the whole statement.

        Returns:
            str | Func: The function body.

        """

        raise_exception = (
            "RAISE EXCEPTION 'pgtrigger: cannot"
            f" {self._verb} rows from % table', TG_TABLE_NAME;"
        )

        if self.for_each is ForEach.ROW:
            return raise_exception

        return Func(f"""
            IF EXISTS (
                SELECT 1
                FROM {self._affected_rows}
                {{where}}
            ) THEN
                {raise_exception}
            END IF;
            RETURN NULL;
        """)  # ruff: ignore[hardcoded-sql-expression]

    @property
    def _affected_rows(self) -> str:
        """
        Name the template placeholder for the transition tables in play.

        Returns:
            str: A `Func` placeholder.

        Raises:
            ValueError: The trigger has no transition tables to test.

        """

        referencing = self.referencing

        if referencing is None:
            raise ValueError(
                f'Statement-level "{self}" has no transition tables to test, so'
                " it cannot tell whether the statement affected anything."
                " Transition tables need a single event."
            )

        if referencing.old and referencing.new:
            return "{changed_rows}"

        return "{new_rows}" if referencing.new else "{old_rows}"

    @property
    def _verb(self) -> str:
        """
        Phrase the events for an error message.

        Returns:
            str: For example, `update or delete`.

        """

        return " or ".join(sorted(e.value.lower() for e in self.events.base_events))
