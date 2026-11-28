"""The .qea fixture builder (PD-24): it cannot invent a column, and it writes what it is told to."""

import sqlite3
from pathlib import Path

import pytest

from tests.generator.uml_qea import DDL, EA_COLUMNS, QeaBuilder

PD3_TABLES = (
    "t_package",
    "t_object",
    "t_attribute",
    "t_connector",
    "t_objectproperties",
    "t_xref",
    "t_diagramobjects",
    "t_diagram",
    "t_connectortag",
    "t_operation",
)


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"pragma table_info({table})")}


def test_ea_columns_and_ddl_cover_the_ten_tables():
    assert set(EA_COLUMNS) == set(PD3_TABLES), "EA_COLUMNS names the ten tables"
    assert set(DDL) == set(PD3_TABLES), "DDL names the ten tables"


@pytest.mark.parametrize("table", PD3_TABLES)
def test_ddl_columns_are_a_subset_of_the_ea_columns(table):
    """TC-12: the fixture cannot invent a column EA does not have."""
    connection = sqlite3.connect(":memory:")
    connection.execute(DDL[table])
    ddl_columns = _columns(connection, table)
    assert ddl_columns, f"{table}: the DDL declares no column"
    assert ddl_columns <= set(EA_COLUMNS[table]), (
        f"{table}: columns EA does not have: {ddl_columns - set(EA_COLUMNS[table])}"
    )


def _row_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {
            table: connection.execute(f"select count(*) from {table}").fetchone()[0]
            for table in PD3_TABLES
        }
    finally:
        connection.close()


def test_a_built_model_reopens_read_only_with_the_rows_written(tmp_path):
    builder = QeaBuilder(tmp_path / "library.qea")
    root = builder.package("MODEL")
    library = builder.package("library", parent=root)
    book = builder.cls(library, "lib:Book", stereotype="root")
    chapter = builder.cls(library, "lib:Chapter")
    shelf = builder.cls(library, "lib:Shelf", abstract=True)
    genre = builder.cls(library, "lib:Genre", object_type="Enumeration")
    builder.attribute(book, "lib:title", "xsd:string", lower="1", upper="1")
    builder.attribute(genre, "lib:poetry", stereotype="enum")
    builder.association(book, chapter, role="lib:chapters", card="0..*")
    builder.dependency(book, genre, role="lib:genre")
    builder.generalisation(shelf, book)
    builder.tag(book, "graph", "lib:books")
    builder.tag(book, "rp_mixins", "long text", memo="long text")
    builder.boundary(diagram=1, package=library)
    builder.place(1, book)
    builder.place(1, chapter)
    path = builder.finish()

    assert path == tmp_path / "library.qea", "finish returns the file's path"
    assert _row_counts(path) == {
        "t_package": 2,
        "t_object": 5,  # three classes, one enumeration, one boundary
        "t_attribute": 2,
        "t_connector": 3,
        "t_objectproperties": 2,
        "t_xref": 0,
        "t_diagramobjects": 3,  # the boundary and its two members
        "t_diagram": 0,
        "t_connectortag": 0,
        "t_operation": 0,
    }, "the rows written are the rows read back"


def test_the_state_machine_helpers_write_the_rows_the_reader_reads(tmp_path):
    builder = QeaBuilder(tmp_path / "loan.qea")
    package = builder.package("library")
    start = builder.state(package, "Start", ntype=3)
    requested = builder.state(package, "requested")
    builder.operation(requested, "entry")
    flow = builder.state_flow(start, requested, tags={"roles": "reader"}, trigger=True)
    builder.statechart("loan", package, [start, requested])
    path = builder.finish()

    assert _row_counts(path) == {
        "t_package": 1,
        "t_object": 2,  # the initial node and one state
        "t_attribute": 0,
        "t_connector": 1,
        "t_objectproperties": 0,
        "t_xref": 1,  # the trigger
        "t_diagramobjects": 2,
        "t_diagram": 1,
        "t_connectortag": 1,
        "t_operation": 1,
    }, "each helper writes its rows"
    assert flow == 1, "the flow's id is its connector id"


def test_builder_methods_return_ids_that_chain(tmp_path):
    builder = QeaBuilder(tmp_path / "ids.qea")
    root = builder.package("MODEL")
    child = builder.package("library", parent=root)
    first = builder.cls(child, "lib:Book")
    second = builder.cls(child, "lib:Chapter")
    path = builder.finish()

    assert len({root, child}) == 2, "two packages, two ids"
    assert len({first, second}) == 2, "two classes, two ids"
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        parent_id = connection.execute(
            "select Parent_ID from t_package where Package_ID = ?", (child,)
        ).fetchone()[0]
        owner = connection.execute(
            "select Package_ID from t_object where Object_ID = ?", (second,)
        ).fetchone()[0]
    finally:
        connection.close()
    assert (parent_id, owner) == (root, child), "the returned ids are the rows' keys"
