from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table

########################################################################################


def build_composite(metadata: MetaData | None = None) -> Table:
    """
    Build a table with a two-column primary key.

    Returns:
        Table: A table whose primary key spans two columns.

    """

    return Table(
        "shipments",
        metadata if metadata is not None else MetaData(),
        Column("order_id", Integer, primary_key=True),
        Column("leg", Integer, primary_key=True),
        Column("delivered", Boolean),
    )


def build_orders(metadata: MetaData | None = None) -> Table:
    """
    Build the table most tests declare against.

    Returns:
        Table: A table with a single-column primary key and an `onupdate`
        column, which is what `exclude_auto` keys off.

    """

    return Table(
        "orders",
        metadata if metadata is not None else MetaData(),
        Column("id", Integer, primary_key=True),
        Column("status", String(32)),
        Column("total", Integer),
        Column("updated_at", Integer, onupdate=1),
    )


def build_scoped(metadata: MetaData | None = None) -> Table:
    """
    Build a table that lives in a named schema.

    Returns:
        Table: A table qualified by schema.

    """

    return Table(
        "invoices",
        metadata if metadata is not None else MetaData(),
        Column("id", Integer, primary_key=True),
        Column("paid", Boolean),
        schema="billing",
    )


def build_quoted(metadata: MetaData | None = None) -> Table:
    """
    Build a table whose names need quoting.

    Returns:
        Table: A table using a reserved word and a mixed-case column.

    """

    return Table(
        "order",
        metadata if metadata is not None else MetaData(),
        Column("id", Integer, primary_key=True),
        Column("Status", String(32), key="status"),
    )
