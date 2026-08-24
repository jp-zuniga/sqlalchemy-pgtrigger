"""
Function bodies that can see the table they are declared on.
"""

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from pgtrigger.aliases import FuncContext

########################################################################################


@final
class Func:
    """
    A `PL/pgSQL` body rendered with access to the table it is declared on.

    The template is filled by `str.format`, so `{` and `}` are significant and
    a literal brace must be doubled.

    Available names:

    - `table`: the SQLAlchemy `Table`
    - `columns.<attr>`: a column's name, quoted only if it needs to be
    - `names.<attr>`: a column's raw, unquoted name
    - `pk`: the table's primary key columns, quoted and comma-separated

    Attributes are keyed by ORM attribute name, which is the column's `key`,
    not necessarily its name in the database.

    ```python
    pgtrigger.Func(
        "INSERT INTO audit (row_id) VALUES (NEW.{columns.id}); RETURN NEW;"
    )
    ```

    A statement-level trigger also gets its transition tables; see
    `Trigger.get_func_context`.
    """

    __slots__ = ("func",)

    def __init__(self, func: str) -> None:
        """
        Store the template.
        """

        self.func = func

    def __eq__(self, other: object) -> bool:
        """
        Compare two templates by their text.

        Returns:
            bool: `True` when both hold the same template.

        """

        return isinstance(other, Func) and self.func == other.func

    def __hash__(self) -> int:
        """
        Hash the template text.

        Returns:
            int: A hash consistent with `__eq__`.

        """

        return hash(self.func)

    def __repr__(self) -> str:
        """
        Show the template.

        Returns:
            str: A reconstructable representation.

        """

        return f"Func({self.func!r})"

    def render(self, **context: FuncContext) -> str:
        """
        Fill the template.

        Returns:
            str: The rendered `PL/pgSQL`.

        Raises:
            ValueError: The template referenced a name that is not available,
                        which most often means a statement-level name was used
                        on a row-level trigger, or a brace was meant literally.

        """

        try:
            return self.func.format(**context)
        except (AttributeError, IndexError, KeyError) as e:
            raise ValueError(
                f"This trigger function template referenced {e}, which is not"
                f" available here. Available names: {', '.join(sorted(context))}."
                " A literal brace must be written as '{{' or '}}'."
            ) from e
