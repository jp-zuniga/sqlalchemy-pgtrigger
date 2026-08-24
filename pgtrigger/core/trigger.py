"""
The trigger itself.
"""

from collections.abc import Mapping
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypedDict, final, override

from sqlalchemy.schema import SchemaItem

import pgtrigger.ddl
import pgtrigger.registry

from pgtrigger.compiler import CompiledTrigger, Upsert
from pgtrigger.config import CONFIG
from pgtrigger.consts import (
    DIGEST_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PGID_LENGTH,
    NAME_PATTERN,
    NEW_ROWS,
    OLD_ROWS,
    PGID_PREFIX,
    REQUIRED_TRIGGER_ATTRS,
)
from pgtrigger.utils import (
    dedent_sql,
    hex_digest,
    pk_columns,
    quote_column,
    quote_table,
    table_uri,
)

from .clauses import Event, Execution, ForEach, Referencing, Time
from .conditions import coerce_condition
from .func import Func
from .proxy import RowScope

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

    from sqlalchemy import Table

    from pgtrigger.aliases import EventClause, FuncContext, FuncSource, Predicate

    from .conditions import Condition

########################################################################################


@final
class TriggerKwargs(TypedDict, total=False):
    """
    The keywords `Trigger` accepts.

    Subclasses that add their own keywords take the rest as `Unpack[TriggerKwargs]`,
    so what they forward stays checked instead of widening to `object`.
    """

    name: str
    time: Time
    events: EventClause
    for_each: ForEach
    execution: Execution
    referencing: Referencing
    condition: Condition | Predicate
    func: FuncSource
    declare: Sequence[tuple[str, str]]


########################################################################################


class Trigger(SchemaItem):
    """
    A PostgreSQL trigger.

    A `Trigger` is a `SchemaItem`, so it is declared in
    `__table_args__` alongside indexes and constraints:

    ```python
    class Orders(Base):
        __tablename__ = "orders"

        id: Mapped[int] = mapped_column(primary_key=True)
        status: Mapped[str]

        __table_args__ = (
            pgtrigger.Protect(events=pgtrigger.Event.DELETE, name="no_deletes"),
        )
    ```

    Every keyword has a matching class attribute, so subclasses set
    their own defaults and users override them per instance:

    ```python
    class Audited(pgtrigger.Trigger):
        time = pgtrigger.Time.AFTER

        events = pgtrigger.Event.INSERT | pgtrigger.Event.UPDATE

        @override
        def get_func(self, table: Table) -> str:
            return "INSERT INTO audit (id) VALUES (NEW.id); RETURN NULL;"
    ```

    The hooks worth overriding are `get_func`, `get_condition`, `get_declare`,
    and `configure`; each receives the table, so a derived trigger can inspect
    columns it was not told about.

    # Statement-level triggers

    Set `for_each=ForEach.STATEMENT` and the trigger fires once per statement
    rather than once per row, which is more efficient when a bulk `UPDATE`
    touches ten thousand rows and the work is the same either way.

    PostgreSQL exposes those rows through transition tables, and they are wired up
    for you: a statement-level `AFTER` trigger on a single event gets a
    `REFERENCING` clause without asking. PostgreSQL also refuses a `WHEN` clause
    there, so a condition is rendered into a `{where}` fragment the function
    body composes with:

    ```python
    pgtrigger.Trigger(
        name="recompute_balances",
        time=pgtrigger.Time.AFTER,
        events=pgtrigger.Event.INSERT,
        for_each=pgtrigger.ForEach.STATEMENT,
        condition=(lambda old, new: new.amount > 0),
        func=pgtrigger.Func(
            "INSERT INTO balances (account_id, balance) "
            "SELECT account_id, SUM(amount) FROM {new_rows} {where} "
            "GROUP BY account_id; "
            "RETURN NULL;"
        ),
    )
    ```
    """

    name: str
    """
    Identifies the trigger within its table. Required.
    """

    time: Time
    """
    Whether to run before, after, or instead of the statement. Required.
    """

    events: EventClause
    """
    Which operations fire the trigger. Required.
    """

    for_each: ForEach = ForEach.ROW
    """
    Whether to fire once per row or once per statement.
    """

    execution: Execution | None = None
    """
    Deferrability. Anything but `None` makes this a constraint trigger.
    """

    referencing: Referencing | None = None
    """
    Transition tables.
    Statement-level triggers only, and derived from `events` when not given.
    """

    condition: Condition | None = None
    """
    Narrows when the trigger fires.
    """

    func: FuncSource | None = None
    """
    `PL/pgSQL` between `BEGIN` and `END`, or a mapping keyed by `ForEach` for a
    trigger that works at either level. Required unless `get_func` is
    overridden.
    """

    declare: Sequence[tuple[str, str]] | None = None
    """
    Variables for the function's `DECLARE` block, as `(name, type)` pairs.
    """

    @override
    def __init__(
        self,
        *,
        name: str | None = None,
        time: Time | None = None,
        events: EventClause | None = None,
        for_each: ForEach | None = None,
        execution: Execution | None = None,
        referencing: Referencing | None = None,
        condition: Condition | Predicate | None = None,
        func: FuncSource | None = None,
        declare: Sequence[tuple[str, str]] | None = None,
    ) -> None:
        """
        Take the clauses, fill in what follows from them, and validate.

        Every keyword defaults to `None`, and a `None` is never assigned, so an
        omitted argument leaves the class attribute of the same name showing
        through, and a subclass default survives.

        That is why there is no way to pass `None` to mean "clear the default".
        `execution=Execution.NOT_DEFERRABLE` says it for the one clause where it
        comes up; `referencing` is derived rather than defaulted, and a subclass
        wanting no condition overrides `get_condition`.

        `name`, `time`, and `events` have no default at all. They are declared
        without a value, so reading them yields the narrow type rather than an
        optional, and `_require` turns a missing one into a clear error rather
        than an `AttributeError` from somewhere further down.
        """

        super().__init__()

        if name is not None:
            self.name = name
        if time is not None:
            self.time = time
        if events is not None:
            self.events = events
        if for_each is not None:
            self.for_each = for_each
        if execution is not None:
            self.execution = execution
        if referencing is not None:
            self.referencing = referencing
        if condition is not None:
            self.condition = coerce_condition(condition)
        if func is not None:
            self.func = func
        if declare is not None:
            self.declare = declare

        self.tables: list[Table] = []

        self._require()
        self._configure()
        self._validate()

    def __repr__(self) -> str:
        """
        Show the class and the trigger's name.

        Returns:
            str: A short representation.

        """

        return f"<{type(self).__name__} {self}>"

    def __str__(self) -> str:
        """
        Name the trigger.

        Returns:
            str: The declared name, or the class name if there is none.

        """

        return getattr(self, "name", None) or type(self).__name__

    ####################################################################################

    def _configure(self) -> None:
        """
        Reconcile clauses that depend on one another, before validation.

        Called at the end of construction. Derives the `REFERENCING` clause of a
        statement-level trigger from its events, since PostgreSQL allows
        transition tables for a single event only.

        Override to derive one clause from another, and call `super()` to keep
        that derivation.
        """

        if (
            self.for_each is ForEach.STATEMENT
            and self.referencing is None
            and self.time is Time.AFTER
        ):
            self.referencing = self._derive_referencing()

    def _derive_referencing(self) -> Referencing | None:
        """
        Pick transition tables to match a single-event statement trigger.

        Returns:
            Referencing | None: The clause, or `None` when the events do not
            permit one.

        """

        match sorted(self.events.base_events):
            case [Event.DELETE]:
                return Referencing(old=OLD_ROWS)
            case [Event.INSERT]:
                return Referencing(new=NEW_ROWS)
            case [Event.UPDATE]:
                return Referencing(new=NEW_ROWS, old=OLD_ROWS)
            case _:
                return None

    def _require(self) -> None:
        """
        Check that every attribute without a default was supplied.

        Raises:
            ValueError: A required attribute is missing.

        """

        for attribute in REQUIRED_TRIGGER_ATTRS:
            if getattr(self, attribute, None) is None:
                raise ValueError(f'Must provide "{attribute}".')

    ####################################################################################

    def _validate(self) -> None:
        """
        Check the declaration against what PostgreSQL will accept.

        Called during construction, because everything caught here would
        otherwise surface as a syntax error at install time, on another machine.

        Raises:
            TypeError: An object of an incorrect type was received.
            ValueError: The combination of clauses is not valid.

        """

        self._validate_name()

        if not isinstance(self.time, Time):
            raise TypeError(f'Invalid "time": {self.time!r}. Expected a Time.')

        if not isinstance(self.for_each, ForEach):
            raise TypeError(
                f'Invalid "for_each": {self.for_each!r}. Expected a ForEach.'
            )

        if self.execution is not None and not isinstance(self.execution, Execution):
            raise ValueError(
                f'Invalid "execution": {self.execution!r}. Expected an Execution.'
            )

        self._validate_events()
        self._validate_referencing()
        self._validate_condition()
        self._validate_deferrability()
        self._validate_instead_of()

    def _validate_name(self) -> None:
        """
        Check the trigger name is short enough and safe unquoted.

        Raises:
            ValueError: The name is unusable.

        """

        if len(self.name) > MAX_NAME_LENGTH:
            raise ValueError(
                f'Trigger name "{self.name}" is {len(self.name)} characters; the'
                f" maximum is {MAX_NAME_LENGTH}. PostgreSQL identifiers stop at"
                f' {MAX_PGID_LENGTH}, and "{PGID_PREFIX}" plus a table digest'
                " consumes the rest."
            )

        if not NAME_PATTERN.match(self.name):
            raise ValueError(
                f'Trigger name "{self.name}" has invalid characters. '
                "Only letters, digits, hyphens, and underscores are allowed."
            )

    def _validate_events(self) -> None:
        """
        Check the rules PostgreSQL puts on `TRUNCATE`.

        Raises:
            ValueError: `TRUNCATE` was used at row level or with a condition.

        """

        if Event.TRUNCATE not in self.events.base_events:
            return

        if self.for_each is not ForEach.STATEMENT:
            raise ValueError(
                "TRUNCATE fires once per statement and has no rows to offer, so"
                " it requires for_each=ForEach.STATEMENT."
            )

        if self.condition is not None:
            raise ValueError(
                "A TRUNCATE trigger cannot have a condition; there is no row to test."
            )

    def _validate_referencing(self) -> None:
        """
        Check the rules PostgreSQL puts on transition tables.

        Raises:
            ValueError: The trigger cannot carry the clause it was given.

        """

        if self.referencing is None:
            return

        if self.for_each is not ForEach.STATEMENT:
            raise ValueError(
                "Transition tables are only available to statement-level triggers; "
                "set for_each=ForEach.STATEMENT."
            )

        if self.time is not Time.AFTER:
            raise ValueError(
                "Transition tables are only populated once the statement has run, "
                "so referencing requires time=Time.AFTER."
            )

        if len(self.events.base_events) > 1:
            raise ValueError(
                "PostgreSQL allows transition tables for a single event only, "
                f"but this trigger fires on {self.events}."
            )

    def _validate_condition(self) -> None:
        """
        Check that a statement-level condition has somewhere to go.

        Raises:
            ValueError: The trigger has a condition but no transition tables.

        """

        if self.condition is None or self.for_each is not ForEach.STATEMENT:
            return

        if self.referencing is None:
            raise ValueError(
                "A statement-level trigger cannot carry a WHEN clause, so its "
                "condition has to be applied to the transition tables instead, "
                f'and "{self}" has none. Transition tables need time=Time.AFTER '
                "and a single event."
            )

    def _validate_deferrability(self) -> None:
        """
        Check the rules PostgreSQL puts on constraint triggers.

        Raises:
            ValueError: The trigger cannot be deferrable as declared.

        """

        if self.execution is None or not self.execution.deferrable:
            return

        if self.time is not Time.AFTER:
            raise ValueError(
                "A deferrable trigger has to run after the statement; set"
                " time=Time.AFTER."
            )

        if self.for_each is not ForEach.ROW:
            raise ValueError(
                "Constraint triggers are row-level; set for_each=ForEach.ROW."
            )

    def _validate_instead_of(self) -> None:
        """
        Check the rules PostgreSQL puts on `INSTEAD OF` triggers.

        Raises:
            ValueError: The trigger cannot be `INSTEAD OF` as declared.

        """

        if self.time is not Time.INSTEAD_OF:
            return

        if self.for_each is not ForEach.ROW:
            raise ValueError(
                "An INSTEAD OF trigger is row-level; set for_each=ForEach.ROW."
            )

        if self.condition is not None:
            raise ValueError("An INSTEAD OF trigger cannot have a condition.")

    ####################################################################################

    @override
    def _set_parent(self, parent: Table, **kwargs: object) -> None:  # ty: ignore[invalid-method-override]
        """
        Attach when declared in `__table_args__`.

        SQLAlchemy calls this for every `SchemaItem` it finds there.
        """

        self.attach(parent)

    def attach(self, table: Table) -> Self:
        """
        Bind this trigger to a table and add it to the registry.

        Idempotent, and one instance may serve several tables, which is what
        makes a trigger on a `declared_attr` mixin work.

        Returns:
            Self: This trigger, for chaining.

        """

        if any(existing is table for existing in self.tables):
            return self

        self.tables.append(table)

        pgtrigger.registry.add(self.uri(table), table=table, trigger=self)
        pgtrigger.ddl.attach(table)

        return self

    def detach(self, table: Table) -> Self:
        """
        Unbind this trigger from a table and drop it from the registry.

        Returns:
            Self: This trigger, for chaining.

        """

        pgtrigger.registry.remove(self.uri(table))

        self.tables = [existing for existing in self.tables if existing is not table]

        return self

    ####################################################################################

    def pgid(self, table: Table) -> str:
        """
        Build the identifier the trigger and its function carry in PostgreSQL.

        Prefixed so introspection can tell our triggers from hand-written ones,
        and suffixed with a digest of the URI so one declaration can serve
        several tables without colliding.

        PostgreSQL folds unquoted identifiers to lower case, so this does too;
        otherwise a mixed-case name would never match on lookup.

        Returns:
            str: The PostgreSQL identifier.

        Raises:
            ValueError: The identifier would exceed the PostgreSQL limit.

        """

        suffix = hex_digest(length=DIGEST_LENGTH, value=self.uri(table))

        pgid = f"{PGID_PREFIX}{self.name}_{suffix}".lower()

        if len(pgid) > MAX_PGID_LENGTH:
            raise ValueError(
                f'Trigger identifier "{pgid}" is {len(pgid)} characters; the'
                f" maximum is {MAX_PGID_LENGTH}."
            )

        return pgid

    def uri(self, table: Table) -> str:
        """
        Build the name this trigger goes by in the registry and to users.

        Of the form `<schema>.table:name`:
        `orders:no_deletes`, `billing.invoices:read_only`.

        Returns:
            str: The trigger URI.

        """

        return f"{table_uri(table)}:{self.name}"

    ####################################################################################

    def get_condition(self, table: Table) -> Condition | None:  # ruff: ignore[unused-method-argument]
        """
        Pick the condition narrowing when the trigger fires.

        Override to derive one from the table.

        Returns:
            Condition | None: The condition, or `None` to fire unconditionally.

        """

        return self.condition

    def get_declare(self, table: Table) -> Sequence[tuple[str, str]]:  # ruff: ignore[unused-method-argument]
        """
        Pick the variables for the function's `DECLARE` block.

        Returns:
            Sequence[tuple[str, str]]: `(name, type)` pairs.

        """

        return self.declare or ()

    def get_func(self, table: Table) -> str | Func:  # ruff: ignore[unused-method-argument]
        """
        Pick the `PL/pgSQL` between `BEGIN` and `END`.

        The body is responsible for returning:
        `NEW` or `OLD` from a row-level `BEFORE` trigger,
        `NULL` from anything else.

        Returns:
            str | Func: The function body.

        Raises:
            ValueError: No body was supplied for this level.

        """

        func = self.func

        if isinstance(func, Mapping):
            if self.for_each not in func:
                supplied = ", ".join(sorted(str(key) for key in func))

                raise ValueError(
                    f'Trigger "{self}" has no function for'
                    f" for_each={self.for_each}. Supplied: {supplied}."
                )

            func = func[self.for_each]

        if func is None:
            raise ValueError(
                f'Trigger "{self}" has no function. Pass func= or override get_func().'
            )

        return func

    def get_func_context(self, table: Table) -> dict[str, FuncContext]:
        """
        Collect the names made available to a `Func` template.

        Always present: `table`, `columns`, `names`, and `pk`.

        A statement-level trigger with transition tables also gets `old_rows`
        and `new_rows`, whichever of the two its event provides, along with
        `changed_rows`, the pair joined on the primary key, and `where`, its
        condition as a `WHERE` clause or the empty string.

        Override to add your own; call `super()` first to keep these.

        Returns:
            dict[str, FuncContext]: Template names.

        """

        context: dict[str, FuncContext] = {
            "table": table,
            "columns": SimpleNamespace(**{
                column.key: quote_column(column) for column in table.columns
            }),
            "names": SimpleNamespace(**{
                column.key: column.name for column in table.columns
            }),
            "pk": ", ".join(quote_column(column) for column in pk_columns(table)),
        }

        if self.for_each is ForEach.STATEMENT and self.referencing is not None:
            context |= self.get_transition_context(table, self.referencing)

        return context

    def get_transition_context(
        self,
        table: Table,
        referencing: Referencing,
    ) -> dict[str, FuncContext]:
        """
        Collect the transition table names, their join, and the `WHERE`.

        Only the sides the trigger's event actually provides are included, so a
        `DELETE` trigger reaching for `new_rows` gets a clear error rather than
        SQL PostgreSQL will reject.

        Returns:
            dict[str, FuncContext]: Statement-level template names.

        """

        context: dict[str, FuncContext] = {"where": self.render_where(table)}

        if referencing.old:
            context["old_rows"] = referencing.old

        if referencing.new:
            context["new_rows"] = referencing.new

        if referencing.old and referencing.new:
            keys = pk_columns(table)
            old_pk = ", ".join(f"{referencing.old}.{quote_column(key)}" for key in keys)
            new_pk = ", ".join(f"{referencing.new}.{quote_column(key)}" for key in keys)
            context["changed_rows"] = (
                f"{referencing.old} JOIN {referencing.new} ON ({old_pk}) = ({new_pk})"
            )

        return context

    ####################################################################################

    def scope(self, table: Table) -> RowScope:
        """
        Pick the rows this trigger's condition resolves against.

        `OLD` and `NEW` at row level; the transition tables at statement level,
        where `OLD` and `NEW` do not exist.

        Returns:
            Scope: The naming environment for conditions.

        """

        if self.for_each is ForEach.STATEMENT and self.referencing is not None:
            return RowScope.transitions(self.referencing, table)

        return RowScope(table=table)

    ####################################################################################

    def render_condition(self, table: Table) -> str:
        """
        Render the `WHEN` clause, if there is one.

        Always empty for a statement-level trigger: PostgreSQL does not allow a
        `WHEN` clause there, so the condition goes into `where` instead.

        Returns:
            str: The clause, or empty.

        """

        if self.for_each is ForEach.STATEMENT:
            return ""

        resolved = self._resolve_condition(table)

        # always parenthesised, because PostgreSQL wants WHEN ( condition ) and
        # a composite already carrying parens around each side,
        # as "(a) AND (b)" does, is not the same thing
        return f"WHEN ({resolved})" if resolved else ""

    def render_declare(self, table: Table) -> str:
        """
        Render the `DECLARE` block, if there is one.

        Returns:
            str: The block, or empty.

        """

        declare = self.get_declare(table)

        if not declare:
            return ""

        variables = " ".join(f"{name} {kind};" for name, kind in declare)

        return f"DECLARE {variables}"

    def render_events(self, table: Table) -> str:
        """
        Render the event list.

        Returns:
            str: Events joined with `OR`.

        """

        return self.events.render(table)

    def render_func(self, table: Table) -> str:
        """
        Render the function body, normalised to column zero.

        The compiler indents it into the surrounding function; keeping the line
        structure means a body that reads well here also reads well in the
        installed trigger.

        Returns:
            str: The `PL/pgSQL` body.

        """

        func = self.get_func(table)

        if isinstance(func, Func):
            func = func.render(**self.get_func_context(table))

        return dedent_sql(func)

    def render_referencing(self, table: Table) -> str:
        """
        Render the `REFERENCING` clause, if there is one.

        Returns:
            str: The clause, or empty.

        """

        return "" if self.referencing is None else self.referencing.render(table)

    def render_where(self, table: Table) -> str:
        """
        Render the condition as a `WHERE` clause over the transition tables.

        Returns:
            str: The clause, or empty.

        """

        resolved = self._resolve_condition(table)

        return f"WHERE {resolved}" if resolved else ""

    def _resolve_condition(self, table: Table) -> str:
        """
        Render the condition against whichever rows this trigger can see.

        Returns:
            str: The condition SQL, or empty.

        """

        condition = self.get_condition(table)

        if condition is None:
            return ""

        return condition.resolve(self.scope(table)).strip()

    ####################################################################################

    def compile(self, table: Table) -> CompiledTrigger:
        """
        Reduce this declaration to SQL.

        Returns:
            CompiledTrigger: The installable form.

        """

        return CompiledTrigger(
            name=self.name,
            upsert=Upsert(
                condition=self.render_condition(table),
                declare=self.render_declare(table),
                events=self.render_events(table),
                execution=self.execution,
                for_each=self.for_each,
                func=self.render_func(table),
                ignore_setting=CONFIG.ignore_setting,
                pgid=self.pgid(table),
                referencing=self.render_referencing(table),
                table=quote_table(table),
                time=self.time,
            ),
        )
