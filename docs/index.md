---
icon: lucide/home
---

# `sqlalchemy-pgtrigger`

> `sqlalchemy` rewrite of [`django-pgtrigger`][og-pgtrigger]

## Installation

```sh
uv add sqlalchemy-pgtrigger
```

Needs Python 3.14+, SQLAlchemy 2.0.52+, and PostgreSQL 13+.
Alembic is optional and only needed if you want triggers in migrations:

```sh
uv add sqlalchemy-pgtrigger[alembic]
```

## Declaring a trigger

Triggers are `SchemaItem`s, so they go in `__table_args__` next to indices and
constraints. The vocabulary follows the `CREATE TRIGGER` grammar, so a declaration
and the statement it produces line up clause for clause.

```python
import pgtrigger

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Document(DeclarativeBase):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str]
    published: Mapped[bool] = mapped_column(default=False)
    deleted: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (
        # once a document is published its body is fixed
        pgtrigger.ReadOnly(
            condition=(lambda old, new: old.published.is_(True)),
            fields=("body",),
            name="published_body_is_final",
        ),
        # a DELETE marks the row rather than removing it
        pgtrigger.SoftDelete(field="deleted", name="mark_deleted"),
    )
```

Conditions are ordinary SQLAlchemy expressions over the `old` and `new` rows,
so the expression language handles the quoting, the types, and the literals.
The first trigger above compiles to:

```sql
WHEN ((OLD.body IS DISTINCT FROM NEW.body) AND (OLD.published IS true))
```

## Installing triggers

`create_all` installs whatever is declared on the tables it creates, which is
usually what you want in tests:

```python
Document.metadata.create_all(engine)
```

Everywhere else, say so explicitly. Every function takes the connectable first;
an `Engine` gets a transaction of its own,
a `Connection` or `Session` joins the one already open:

```python
from pgtrigger.installation import install, status, uninstall

install(engine)  # everything registered
install(engine, "documents:mark_deleted")  # one trigger
install(session, "documents:*")  # one table
status(engine)  # declared vs installed
```

To keep triggers in migrations instead,
import the Alembic integration from your `env.py`,
and let `pgtrigger.migrations.autogenerate` find them:

```python
# alembic/env.py
import pgtrigger.migrations
```

Each installed trigger carries a fingerprint of its own definition, so
`autogenerate` diffs declarations against the database rather than against
migration state. A revision records the finished SQL, so editing a
declaration later never rewrites migration history.

## Acknowledgements

A special thanks to the team at [Ambition][ambition] and
all the contributors behind [`django-pgtrigger`][og-pgtrigger].

Their excellent work on managing PostgreSQL triggers in Django
served as the architectural foundation for this library.

## License

This project is [licensed under the BSD-3-Clause license][license].
