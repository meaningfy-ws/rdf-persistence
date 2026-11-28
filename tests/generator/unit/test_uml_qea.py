"""The .qea reader (PD-3, PD-4): the subtree, the usage errors, the tagged values, the boundaries."""

import os
import sqlite3
from pathlib import Path

import pytest

from rdf_persistence_generation.exceptions import QeaUsageError
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    UmlComposition,
    UmlLinkKind,
    UmlModel,
    UmlRule,
)
from rdf_persistence_generation.problems import format_problem
from rdf_persistence_generation.uml.qea import TABLE_COLUMNS, read_qea
from tests.generator.uml_qea import QeaBuilder

ROOT = "MODEL/library"


def build_library(tmp_path: Path) -> tuple[QeaBuilder, dict[str, int]]:
    """MODEL/library (Book, Chapter, Genre) with a child package, a sibling and a namesake."""
    builder = QeaBuilder(tmp_path / "library.qea")
    ids: dict[str, int] = {}
    ids["model"] = builder.package("MODEL")
    ids["library"] = builder.package("library", parent=ids["model"], note="The library.")
    ids["rare"] = builder.package("rare-books", parent=ids["library"])
    ids["other"] = builder.package("other", parent=ids["model"])
    ids["book"] = builder.cls(ids["library"], "lib:Book", stereotype="root", note="A book.")
    ids["chapter"] = builder.cls(ids["library"], "lib:Chapter", abstract=True)
    ids["genre"] = builder.cls(ids["library"], "lib:Genre", object_type="Enumeration")
    ids["folio"] = builder.cls(ids["rare"], "lib:Folio")
    ids["stray"] = builder.cls(ids["other"], "lib:Stray")
    return builder, ids


def read(builder: QeaBuilder, package: str = ROOT, excluded: tuple[str, ...] = ()):
    return read_qea(builder.finish(), package, excluded)


def names(model: UmlModel) -> list[str]:
    return [item.name for item in model.uml_classes or []]


def as_model(result: UmlModel | list[CheckProblem]) -> UmlModel:
    assert isinstance(result, UmlModel), f"problems found: {[format_problem(p) for p in result]}"
    return result


def as_problems(result: UmlModel | list[CheckProblem]) -> list[str]:
    assert not isinstance(result, UmlModel), "the reader found no problem"
    return [format_problem(problem) for problem in result]


# --- TC-1: the subtree ------------------------------------------------------------------------


def test_the_model_holds_the_subtree_classes_only(tmp_path):
    builder, _ = build_library(tmp_path)
    model = as_model(read(builder))
    assert names(model) == ["lib:Book", "lib:Chapter", "lib:Folio", "lib:Genre"], names(model)


def test_the_model_holds_the_subtree_packages_with_their_notes(tmp_path):
    builder, _ = build_library(tmp_path)
    model = as_model(read(builder))
    assert [(p.name, p.note) for p in model.uml_packages] == [
        ("library", "The library."),
        ("rare-books", None),
    ], "the subtree's packages come with their notes"


def test_a_package_is_named_by_its_name_when_the_name_is_unique(tmp_path):
    builder, _ = build_library(tmp_path)
    assert names(as_model(read(builder, package="rare-books"))) == ["lib:Folio"], (
        "the unique name picks the package"
    )


def test_an_excluded_package_leaves_out_its_subtree(tmp_path):
    builder, _ = build_library(tmp_path)
    model = as_model(read(builder, excluded=("MODEL/library/rare-books",)))
    assert "lib:Folio" not in names(model), "the excluded package's class is left out"
    assert [p.name for p in model.uml_packages] == ["library"], "so is the package"


def test_a_class_carries_the_columns_the_reader_copies(tmp_path):
    builder, ids = build_library(tmp_path)
    model = as_model(read(builder))
    book, chapter = model.uml_classes[0], model.uml_classes[1]
    assert (book.object_id, book.object_type, book.uml_stereotype, book.note) == (
        ids["book"],
        "Class",
        "root",
        "A book.",
    ), "id, type, stereotype and note are copied"
    assert (book.package_id, book.is_abstract, chapter.is_abstract) == (
        ids["library"],
        False,
        True,
    ), "package and abstractness are copied"


def test_attributes_come_in_position_order_with_their_raw_bounds(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.attribute(ids["book"], "lib:title", "xsd:string", lower="1", upper="1", pos=2)
    builder.attribute(ids["book"], "lib:subtitle", "xsd:string", lower="0", upper="*", pos=1)
    model = as_model(read(builder))
    attributes = model.uml_classes[0].uml_attributes
    assert [(a.name, a.lower_bound, a.upper_bound) for a in attributes] == [
        ("lib:subtitle", "0", "*"),
        ("lib:title", "1", "1"),
    ], "attributes follow their position, bounds as written"


def test_links_are_those_touching_a_converted_class_with_raw_cards(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.association(ids["book"], ids["chapter"], role="lib:chapters", card="1..*")
    builder.association(ids["book"], ids["stray"], role="lib:stray", card="")
    builder.association(ids["stray"], ids["stray"], role="lib:self", card="1")
    builder.dependency(ids["book"], ids["genre"], role="lib:genre")
    builder.generalisation(ids["folio"], ids["book"])
    model = as_model(read(builder))
    summary = [
        (link.link_kind, link.target_id, link.target_role, link.target_card)
        for link in model.uml_links
    ]
    assert summary == [
        (UmlLinkKind.ASSOCIATION, ids["chapter"], "lib:chapters", "1..*"),
        (UmlLinkKind.ASSOCIATION, ids["stray"], "lib:stray", None),
        (UmlLinkKind.DEPENDENCY, ids["genre"], "lib:genre", None),
        (UmlLinkKind.GENERALISATION, ids["book"], None, None),
    ], "links touching a converted class are read, with raw cardinalities"


def test_direction_is_read_from_the_connector(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.association(ids["book"], ids["chapter"], role="lib:chapters", card="0..*")
    builder.association(
        ids["book"], ids["folio"], role="lib:folios", card="0..*", direction="Bi-Directional"
    )
    model = as_model(read(builder))
    assert [link.direction for link in model.uml_links] == [
        "Source -> Destination",
        "Bi-Directional",
    ], "each link carries the connector's direction"


def test_the_result_is_sorted_whatever_the_order_the_rows_were_written_in(tmp_path):
    builder = QeaBuilder(tmp_path / "order.qea")
    top = builder.package("MODEL")
    pkg = builder.package("library", parent=top)
    for name in ("lib:Zebra", "lib:Apple", "lib:Mango"):
        builder.cls(pkg, name)
    assert names(as_model(read(builder, package="library"))) == [
        "lib:Apple",
        "lib:Mango",
        "lib:Zebra",
    ], "classes are sorted by name"


# --- model problems (A-9) ----------------------------------------------------------------------


def test_an_unexpected_object_type_is_a_no_rule_problem(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.cls(ids["library"], "lib:Printer", object_type="Component")
    builder.cls(ids["library"], "lib:Sketch", object_type="Note")
    builder.cls(ids["library"], "lib:Loose", object_type="Package")
    lines = as_problems(read(builder))
    assert lines == ["[no_rule] lib:Printer: Component object: no rule converts it"], (
        f"only the component is a problem, notes and packages are ignored: {lines}"
    )


def _run_state(*variables: tuple[str, str]) -> str:
    """A ``RunState`` as EA writes it: one ``@VAR`` block per variable, ``Op`` always ``=``."""
    return "".join(f"@VAR;Variable={name};Value={value};Op==;@ENDVAR;" for name, value in variables)


def test_an_object_reads_into_a_record_with_its_classifier_and_run_values(tmp_path):
    builder, ids = build_library(tmp_path)
    role_definition = builder.cls(ids["library"], "rp:RoleDefinition")
    owner = builder.object_(
        ids["library"],
        "owner at tenant",
        role_definition,
        _run_state(("role", "owner"), ("level", "tenant"), ("actions", "read,modify")),
    )
    model = as_model(read(builder))
    found = [(o.object_id, o.uml_name, o.classifier_id, o.package_path) for o in model.uml_objects]
    assert found == [(owner, "owner at tenant", role_definition, ROOT)], (
        "an Object in the subtree is one record, named, classified and placed, not a problem"
    )
    assert [(v.variable, v.value, v.operator) for v in model.uml_objects[0].run_values] == [
        ("role", "owner", "="),
        ("level", "tenant", "="),
        ("actions", "read,modify", "="),
    ], "its RunState blocks are copied as written, in order, unvalidated"


def test_an_object_without_a_classifier_or_a_run_state_keeps_them_absent(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.object_(ids["library"], "bare", 0, None)
    record = as_model(read(builder)).uml_objects[0]
    assert (record.classifier_id, record.run_values) == (None, []), (
        "classifier 0 is no classifier and an empty RunState has no values"
    )


@pytest.mark.parametrize(
    ("run_state", "rest"),
    [
        pytest.param("@VAR;Variable=role;Value=owner;Op==;@ENDVAR;", None, id="no text outside"),
        pytest.param(
            "  stray @VAR;Variable=role;Value=owner;Op==;@ENDVAR; text\n"
            "@VAR;Variable=level;Value=tenant;Op==;@ENDVAR;  ",
            "stray  text",
            id="the text left when the blocks are removed, stripped",
        ),
        pytest.param("only text", "only text", id="text and no block"),
        pytest.param("  \n ", None, id="blank text is absent"),
        pytest.param(None, None, id="no run state"),
    ],
)
def test_an_object_keeps_the_text_outside_its_run_state_blocks(tmp_path, run_state, rest):
    builder, ids = build_library(tmp_path)
    builder.object_(ids["library"], "obj", 0, run_state)
    record = as_model(read(builder)).uml_objects[0]
    assert record.run_state_rest == rest, (
        f"the text outside the @VAR blocks is copied for the role rule to judge (D-4): "
        f"{record.run_state_rest!r}"
    )


def test_an_object_outside_the_subtree_is_not_read(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.object_(ids["other"], "elsewhere", 0, _run_state(("role", "owner")))
    assert as_model(read(builder)).uml_objects == [], "only the converted subtree is read"


def test_an_association_class_is_a_no_rule_problem(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.association(ids["book"], ids["chapter"], role="lib:x", card="1", sub_type="Class")
    builder.association(ids["book"], ids["folio"], role="lib:y", card="1", pdata1=str(ids["genre"]))
    lines = as_problems(read(builder))
    assert len(lines) == 2, f"both association classes are problems: {lines}"
    assert all(line.startswith("[no_rule] lib:Book") for line in lines), f"on Book: {lines}"
    assert all("association class: no rule converts it" in line for line in lines), (
        f"each names the association class: {lines}"
    )


def test_two_stereotypes_in_xref_are_a_no_rule_problem(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.extra_stereotypes(ids["book"], "root", "loaded graph")
    builder.extra_stereotypes(ids["chapter"], "one")
    assert as_problems(read(builder)) == [
        "[no_rule] lib:Book: two stereotypes (loaded graph, root): no rule converts it"
    ], "a class with two stereotypes is a problem, one with a single extra is not"


def test_all_problems_are_collected_and_sorted(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.cls(ids["library"], "lib:Zed", object_type="Interface")
    builder.cls(ids["library"], "lib:Abe", object_type="Component")
    lines = as_problems(read(builder))
    assert lines == [
        "[no_rule] lib:Abe: Component object: no rule converts it",
        "[no_rule] lib:Zed: Interface object: no rule converts it",
    ], "every problem is collected, sorted by element"
    assert {p.rule for p in read_qea(builder.path, ROOT, ())} == {UmlRule.NO_RULE.value}, (
        "every problem has the no_rule rule"
    )


# --- TC-3: tagged values -----------------------------------------------------------------------


def test_a_memo_tag_takes_its_text_from_the_notes(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.tag(ids["book"], "rp_path", "", memo="books")
    builder.tag(ids["book"], "graph", "lib:books")
    model = as_model(read(builder))
    assert [(t.owner_id, t.name, t.tag_value) for t in model.uml_tagged_values] == [
        (ids["book"], "graph", "lib:books"),
        (ids["book"], "rp_path", "books"),
    ], "the memo tag's text is its notes"


def test_a_package_carries_its_own_object_and_that_object_s_tags_are_read(tmp_path):
    builder, ids = build_library(tmp_path)
    library_element = builder.package_element(ids["library"])
    rare_element = builder.package_element(ids["rare"])
    other_element = builder.package_element(ids["other"])
    builder.tag(library_element, "module_kind", "access")
    builder.tag(other_element, "module_kind", "access")
    model = as_model(read(builder))
    assert {p.name: p.object_id for p in model.uml_packages} == {
        "library": library_element,
        "rare-books": rare_element,
    }, "each converted package names the object EA draws it as (same ea_guid)"
    assert [(t.owner_id, t.name, t.tag_value) for t in model.uml_tagged_values] == [
        (library_element, "module_kind", "access"),
    ], "a converted package's tags are read, an outside package's are not"


def test_tags_of_objects_outside_the_subtree_are_not_read(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.tag(ids["stray"], "graph", "lib:x")
    assert as_model(read(builder)).uml_tagged_values == [], "an outside class's tags are not read"


# --- the far end of a link that is not converted (D-17) -----------------------------------------


def outside_names(model: UmlModel) -> list[str]:
    return [item.name for item in model.uml_outside_classes or []]


def test_an_association_to_a_class_outside_the_subtree_names_it_without_attributes(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.attribute(ids["stray"], "lib:secret", "xsd:string")
    builder.association(ids["book"], ids["stray"], role="lib:stray", card="0..1")
    model = as_model(read(builder))
    (stray,) = model.uml_outside_classes
    assert (stray.object_id, stray.name, stray.object_type, stray.package_id) == (
        ids["stray"],
        "lib:Stray",
        "Class",
        ids["other"],
    ), "the outside class is named with its package"
    assert not stray.uml_attributes, "it has no attributes"
    assert "lib:Stray" not in names(model), "it is not a converted class"


def test_an_outside_class_carries_the_columns_the_reader_copies(tmp_path):
    builder, ids = build_library(tmp_path)
    ids["ghost"] = builder.cls(
        ids["other"], "lib:Ghost", stereotype="loaded graph", abstract=True, note="A ghost."
    )
    builder.association(ids["book"], ids["ghost"], role="lib:ghost", card="0..1")
    (ghost,) = as_model(read(builder)).uml_outside_classes
    assert (ghost.uml_stereotype, ghost.note, ghost.is_abstract) == (
        "loaded graph",
        "A ghost.",
        True,
    ), "stereotype, note and abstractness are copied"
    assert ghost.ea_guid == f"{{GUID-{ids['ghost']}}}", "the GUID is copied"


def test_an_association_to_a_class_in_an_excluded_package_names_it_too(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.attribute(ids["folio"], "lib:leaf", "xsd:string")
    builder.association(ids["book"], ids["folio"], role="lib:folio", card="0..1")
    model = as_model(read(builder, excluded=("MODEL/library/rare-books",)))
    (folio,) = model.uml_outside_classes
    assert (folio.name, folio.package_id) == ("lib:Folio", ids["rare"]), "the class is named"
    assert not folio.uml_attributes, "it has no attributes"
    assert [p.name for p in model.uml_packages] == ["library"], "its package is not converted"


def test_a_dependency_to_an_outside_enumeration_names_it(tmp_path):
    builder, ids = build_library(tmp_path)
    ids["status"] = builder.cls(ids["other"], "lib:Status", object_type="Enumeration")
    builder.dependency(ids["book"], ids["status"], role="lib:status")
    (status,) = as_model(read(builder)).uml_outside_classes
    assert (status.name, status.object_type) == ("lib:Status", "Enumeration"), "the enum is named"


def test_a_generalisation_to_an_outside_class_names_it(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.generalisation(ids["book"], ids["stray"])
    assert outside_names(as_model(read(builder))) == ["lib:Stray"], "the parent is named"


def test_a_class_reached_by_two_links_appears_once_in_object_id_order(tmp_path):
    builder, ids = build_library(tmp_path)
    ids["late"] = builder.cls(ids["other"], "lib:Aardvark")
    builder.association(ids["book"], ids["late"], role="lib:late", card="0..1")
    builder.association(ids["chapter"], ids["stray"], role="lib:stray", card="0..1")
    builder.generalisation(ids["chapter"], ids["late"])
    builder.generalisation(ids["book"], ids["stray"])
    model = as_model(read(builder))
    assert [c.object_id for c in model.uml_outside_classes] == [ids["stray"], ids["late"]], (
        "each outside class once, in object-id order"
    )


def test_a_link_between_outside_classes_names_none(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.association(ids["stray"], ids["stray"], role="lib:self", card="1")
    assert as_model(read(builder)).uml_outside_classes in (None, []), "no outside class is named"


def test_the_outside_packages_hold_what_the_outside_classes_need_beyond_the_converted_ones(
    tmp_path,
):
    builder, ids = build_library(tmp_path)
    builder.association(ids["book"], ids["stray"], role="lib:stray", card="0..1")
    builder.association(ids["book"], ids["folio"], role="lib:folio", card="0..1")
    model = as_model(read(builder, excluded=("MODEL/library/rare-books",)))
    assert [(p.name, p.package_id, p.parent_id) for p in model.uml_outside_packages] == [
        ("MODEL", ids["model"], None),
        ("rare-books", ids["rare"], ids["library"]),
        ("other", ids["other"], ids["model"]),
    ], "the outside packages are those the outside classes need"
    assert [p.name for p in model.uml_packages] == ["library"], "the converted packages"


# --- usage errors (matrix, exit 2) -------------------------------------------------------------


def test_an_exclude_path_that_matches_no_package_is_a_usage_error(tmp_path):
    builder, _ = build_library(tmp_path)
    with pytest.raises(QeaUsageError) as error:
        read(builder, excluded=("MODEL/library/nowhere",))
    assert error.value.message == "no package MODEL/library/nowhere under library", (
        error.value.message
    )


@pytest.mark.parametrize("kind", ["absent", "folder"])
def test_a_missing_path_is_named_as_missing(tmp_path, kind):
    path = tmp_path / "absent.qea"
    if kind == "folder":
        path.mkdir()
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path}: no such file", error.value.message


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_an_unreadable_file_is_a_read_error(tmp_path):
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    path.chmod(0)
    try:
        with pytest.raises(QeaUsageError) as error:
            read_qea(path, ROOT, ())
    finally:
        path.chmod(0o600)
    assert error.value.message == f"{path} cannot be read: Permission denied", error.value.message


def test_a_corrupt_page_is_a_read_error_not_a_traceback(tmp_path):
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    data = bytearray(path.read_bytes())
    for offset in range(4096, len(data)):
        data[offset] = 0xFF  # keep page 1 (the header and the schema), wreck the rest
    path.write_bytes(bytes(data))
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message.startswith(f"{path} cannot be read: "), error.value.message


def _wal_model(tmp_path: Path) -> Path:
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    connection = sqlite3.connect(path)
    connection.execute("pragma journal_mode=wal")
    connection.commit()
    connection.close()  # the last connection closing removes -wal and -shm
    for side in ("-wal", "-shm"):
        Path(f"{path}{side}").unlink(missing_ok=True)
    return path


def test_reading_a_wal_model_leaves_no_side_files(tmp_path):
    path = _wal_model(tmp_path)
    before = path.read_bytes()
    as_model(read_qea(path, ROOT, ()))
    side_files = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(path.name + "-"))
    assert side_files == [], f"the reader left {side_files}"
    assert path.read_bytes() == before, "the reader changed the file"


def test_a_wal_model_with_a_wal_file_is_read(tmp_path):
    path = _wal_model(tmp_path)
    holder = sqlite3.connect(path)
    holder.execute("pragma journal_mode=wal")
    holder.execute("update t_package set Notes = 'edited' where Name = 'library'")
    holder.commit()  # the change sits in the -wal file while this connection stays open
    try:
        assert Path(f"{path}-wal").exists(), "the test needs a -wal file"
        model = as_model(read_qea(path, ROOT, ()))
    finally:
        holder.close()
    notes = [p.note for p in model.uml_packages or [] if p.name == "library"]
    assert notes == ["edited"], f"the reader missed the -wal content: {notes}"


@pytest.mark.parametrize("kind", ["view", "trigger", "index"])
def test_a_view_named_like_a_table_is_refused(tmp_path, kind):
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    _alter(path, "DROP TABLE t_xref")
    if kind == "view":
        _alter(path, "CREATE VIEW t_xref AS SELECT 1 AS Client, 1 AS Name, 1 AS Description")
    elif kind == "index":
        _alter(path, "CREATE INDEX t_xref ON t_object (Name)")
    else:
        _alter(
            path,
            "CREATE TRIGGER t_xref AFTER INSERT ON t_object BEGIN SELECT 1; END",
        )
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path} has no table t_xref", error.value.message


def test_a_text_file_is_not_an_ea_file(tmp_path):
    path = tmp_path / "text.qea"
    path.write_text("this is not a database, and it is long enough to look like a header\n" * 8)
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path} is not an Enterprise Architect .qea (SQLite) file", (
        error.value.message
    )


def _alter(path: Path, statement: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute(statement)
    connection.commit()
    connection.close()


def test_a_missing_table_is_named(tmp_path):
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    _alter(path, "DROP TABLE t_xref")
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path} has no table t_xref", error.value.message


def test_a_missing_column_is_named_with_its_table(tmp_path):
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    _alter(path, "ALTER TABLE t_connector DROP COLUMN Direction")
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path}: table t_connector has no column Direction", (
        error.value.message
    )


def test_a_missing_run_state_column_is_named_with_its_table(tmp_path):
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    _alter(path, "ALTER TABLE t_object DROP COLUMN RunState")
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path}: table t_object has no column RunState", (
        error.value.message
    )


def test_an_unknown_package_is_named(tmp_path):
    builder, _ = build_library(tmp_path)
    with pytest.raises(QeaUsageError) as error:
        read(builder, package="nothing")
    assert error.value.message == "no package nothing", error.value.message


def test_an_ambiguous_package_lists_the_paths_and_a_path_resolves_it(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.package("library", parent=ids["other"])
    path = builder.finish()
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, "library", ())
    assert error.value.message == (
        "package library is ambiguous: MODEL/library, MODEL/other/library; name it by path"
    ), error.value.message
    assert "lib:Book" in names(as_model(read_qea(path, "MODEL/library", ()))), (
        "the path form resolves the ambiguity"
    )


def test_the_database_is_opened_read_only(tmp_path, monkeypatch):
    builder, _ = build_library(tmp_path)
    path = builder.finish()
    before = path.read_bytes()
    real_connect = sqlite3.connect
    attempts: list[str] = []

    def probing_connect(*args, **kwargs):
        """Open as the reader does, then try to write through that very connection."""
        connection = real_connect(*args, **kwargs)
        try:
            connection.execute("create table probe (x)")
            connection.commit()
            attempts.append("written")
        except sqlite3.OperationalError as error:
            attempts.append(str(error))
        return connection

    monkeypatch.setattr(sqlite3, "connect", probing_connect)
    read_qea(path, ROOT, ())
    assert attempts == ["attempt to write a readonly database"], (
        f"the reader's connection must refuse a write, it did: {attempts}"
    )
    assert path.read_bytes() == before, "the reader changed the file"


# --- connectors the reader does not map (D-17) -------------------------------------------------


def test_an_unknown_connector_type_touching_a_class_is_a_no_rule_problem(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.connector("Realisation", ids["book"], ids["chapter"])
    lines = as_problems(read(builder))
    assert lines == [
        "[no_rule] lib:Book -> lib:Chapter: Realisation connector: no rule converts it"
    ], f"an unknown connector type touching a converted class is a problem: {lines}"


def test_an_unknown_connector_type_away_from_every_converted_class_is_not_read(tmp_path):
    builder, ids = build_library(tmp_path)
    ids["other_stray"] = builder.cls(ids["other"], "lib:Other")
    builder.connector("Realisation", ids["stray"], ids["other_stray"])
    model = as_model(read(builder))
    assert not model.uml_links, "a connector between two outside classes is not a link"


@pytest.mark.parametrize("object_type", ["Note", "Boundary", "Text", "Package"])
def test_a_connector_to_a_note_boundary_text_or_package_is_skipped(tmp_path, object_type):
    builder, ids = build_library(tmp_path)
    ignored = builder.cls(ids["library"], "lib:Ignored", object_type=object_type)
    builder.connector("NoteLink", ids["book"], ignored)
    builder.connector("Realisation", ignored, ids["book"])
    builder.association(ids["book"], ignored, role="lib:note", card="0..1")
    builder.association(ignored, ids["book"], role="lib:back", card="0..1")
    builder.dependency(ids["book"], ignored, role="lib:dep")
    model = as_model(read(builder))
    assert not model.uml_links, f"a {object_type} end makes no link and no problem"
    assert not model.uml_outside_classes, f"a {object_type} is not named as an outside class"


# --- compositions (PD-1, D-5) ------------------------------------------------------------------

DRAWINGS = [
    pytest.param(False, id="whole_to_part"),
    pytest.param(True, id="part_to_whole"),
]


@pytest.mark.parametrize("part_to_whole", DRAWINGS)
def test_a_composition_reads_its_whole_from_the_diamond_end(tmp_path, part_to_whole):
    builder, ids = build_library(tmp_path)
    connector = builder.aggregation(ids["book"], ids["chapter"], part_to_whole=part_to_whole)
    model = as_model(read(builder))
    assert model.uml_compositions == [
        UmlComposition(
            composition_id=connector, whole_id=ids["book"], part_id=ids["chapter"], own_graph=False
        )
    ], "either drawing gives the same whole and part"
    assert not model.uml_links, "a composition is a record of its own, not a link"


@pytest.mark.parametrize("sub_type", ["Strong", "Weak", None])
def test_subtype_is_not_read(tmp_path, sub_type):
    builder, ids = build_library(tmp_path)
    connector = builder.aggregation(ids["book"], ids["chapter"], sub_type=sub_type)
    model = as_model(read(builder))
    assert model.uml_compositions == [
        UmlComposition(
            composition_id=connector, whole_id=ids["book"], part_id=ids["chapter"], own_graph=False
        )
    ], f"SubType {sub_type!r} must not change the record (D-5)"


BOTH_ENDS_MARKED = "composition with no single diamond end: no rule converts it"
SHARED = "a shared aggregation; draw a composition (strong) or a plain association"
REFUSED_AGGREGATIONS = [
    pytest.param(
        {"shared": True},
        f"[boundary_owned] lib:Book -> lib:Chapter: {SHARED}",
        id="shared_whole_to_part",
    ),
    pytest.param(
        {"shared": True, "part_to_whole": True},
        f"[boundary_owned] lib:Chapter -> lib:Book: {SHARED}",
        id="shared_part_to_whole",
    ),
    pytest.param(
        {"ends": (2, 1)},
        f"[boundary_owned] lib:Book -> lib:Chapter: {SHARED}",
        id="shared_beside_a_composition_end",
    ),
    pytest.param(
        {"ends": (0, 0)},
        f"[no_rule] lib:Book -> lib:Chapter: {BOTH_ENDS_MARKED}",
        id="no_end_marked",
    ),
    pytest.param(
        {"ends": (None, None)},
        f"[no_rule] lib:Book -> lib:Chapter: {BOTH_ENDS_MARKED}",
        id="no_end_marked_null",
    ),
    pytest.param(
        {"ends": (2, 2)},
        f"[no_rule] lib:Book -> lib:Chapter: {BOTH_ENDS_MARKED}",
        id="both_ends_marked",
    ),
    pytest.param(
        {"ends": (3, 0)},
        "[no_rule] lib:Book -> lib:Chapter: aggregate value 3: no rule converts it",
        id="other_value_at_source",
    ),
    pytest.param(
        {"ends": (0, -1)},
        "[no_rule] lib:Book -> lib:Chapter: aggregate value -1: no rule converts it",
        id="other_value_at_destination",
    ),
]


@pytest.mark.parametrize(("drawing", "expected"), REFUSED_AGGREGATIONS)
def test_an_aggregation_without_one_diamond_end_is_refused(tmp_path, drawing, expected):
    builder, ids = build_library(tmp_path)
    builder.aggregation(ids["book"], ids["chapter"], **drawing)
    assert as_problems(read(builder)) == [expected], "exactly this problem, naming the connector"


@pytest.mark.parametrize(
    ("stereotype", "own_graph"),
    [("own graph", True), ("Own Graph", True), (" own graph ", True), (None, False), ("x", False)],
)
def test_own_graph_is_read_from_the_stereotype(tmp_path, stereotype, own_graph):
    builder, ids = build_library(tmp_path)
    builder.aggregation(ids["book"], ids["chapter"], stereotype=stereotype)
    [composition] = as_model(read(builder)).uml_compositions
    assert composition.own_graph is own_graph, f"stereotype {stereotype!r}"
    assert composition.uml_stereotype == stereotype, (
        "the stereotype is carried as written, for the converter to judge"
    )


@pytest.mark.parametrize("part_to_whole", DRAWINGS)
def test_a_composition_role_is_the_one_at_the_part_end(tmp_path, part_to_whole):
    builder, ids = build_library(tmp_path)
    builder.aggregation(ids["book"], ids["chapter"], part_to_whole=part_to_whole, role="lib:parts")
    [composition] = as_model(read(builder)).uml_compositions
    assert composition.role == "lib:parts", "the role is read at the part's end, whichever way"


def test_a_composition_end_outside_the_subtree_is_listed(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.aggregation(ids["book"], ids["stray"])
    model = as_model(read(builder))
    assert [c.name for c in model.uml_outside_classes] == ["lib:Stray"], (
        "the far end is listed, so the converter can name it (A-9)"
    )
    assert [(c.whole_id, c.part_id) for c in model.uml_compositions] == [
        (ids["book"], ids["stray"])
    ], "the composition is kept"


def test_a_composition_between_two_outside_classes_is_not_read(tmp_path):
    builder, ids = build_library(tmp_path)
    other = builder.cls(ids["other"], "lib:Other")
    builder.aggregation(ids["stray"], other)
    model = as_model(read(builder))
    assert not model.uml_compositions, "a connector away from every converted class is not read"
    assert not model.uml_outside_classes, "and lists no class"


# --- Realisation of an Object (PD-11, A-20) ----------------------------------------------------


@pytest.mark.parametrize("spelling", ["Realisation", "Realization"])
@pytest.mark.parametrize("from_target", [False, True], ids=["from_object", "from_class"])
def test_a_realisation_from_an_object_is_read_as_realised(tmp_path, from_target, spelling):
    builder, ids = build_library(tmp_path)
    obj = builder.object_(ids["library"], "librarian", None)
    builder.realisation(obj, ids["chapter"], from_target=from_target, spelling=spelling)
    model = as_model(read(builder))
    assert [o.realised_ids for o in model.uml_objects] == [[ids["chapter"]]], (
        "the object's class is the target, whichever way the connector is drawn"
    )
    assert not model.uml_links, "a Realisation is never a link"


def test_two_realisations_are_both_read_sorted(tmp_path):
    builder, ids = build_library(tmp_path)
    obj = builder.object_(ids["library"], "librarian", None)
    builder.realisation(obj, ids["chapter"])
    builder.realisation(obj, ids["book"])
    [read_object] = as_model(read(builder)).uml_objects
    assert read_object.realised_ids == sorted([ids["book"], ids["chapter"]]), "both, by id"


def test_an_object_with_no_realisation_has_none(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.object_(ids["library"], "librarian", ids["book"])
    [read_object] = as_model(read(builder)).uml_objects
    assert not read_object.realised_ids, "no Realisation, nothing realised"


def test_a_realisation_from_a_class_stays_a_problem(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.object_(ids["library"], "librarian", None)
    builder.realisation(ids["book"], ids["chapter"])
    assert as_problems(read(builder)) == [
        "[no_rule] lib:Book -> lib:Chapter: Realisation connector: no rule converts it"
    ], "only an Object may realise"


@pytest.mark.parametrize(
    "package", ["rare", "other"], ids=["excluded_package", "outside_the_subtree"]
)
def test_an_object_not_converted_is_skipped_with_its_realisation(tmp_path, package):
    builder, ids = build_library(tmp_path)
    obj = builder.object_(ids[package], "librarian", None)
    builder.realisation(obj, ids["book"])
    model = as_model(read(builder, excluded=("MODEL/library/rare-books",)))
    assert not model.uml_objects, "the Object is not of the converted packages"
    assert not model.uml_links, "and its Realisation is no link and no problem (A-20)"


def test_a_realisation_to_a_target_outside_the_subtree_is_kept(tmp_path):
    builder, ids = build_library(tmp_path)
    obj = builder.object_(ids["library"], "librarian", None)
    builder.realisation(obj, ids["stray"])
    model = as_model(read(builder))
    assert [o.realised_ids for o in model.uml_objects] == [[ids["stray"]]], "the target is kept"
    assert [c.name for c in model.uml_outside_classes] == ["lib:Stray"], (
        "and listed as an outside class, so the converter can name it"
    )


# --- PD-7, PD-18: a boundary is read by name and package, no geometry ----------------------------


def test_the_reader_reads_no_geometry(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.boundary(diagram=1, package=ids["library"], name="Aggregate: Book")
    path = builder.finish()
    with sqlite3.connect(path) as connection:
        for column in ("RectTop", "RectLeft", "RectRight", "RectBottom"):
            connection.execute(f"ALTER TABLE t_diagramobjects DROP COLUMN {column}")
    model = as_model(read_qea(path, ROOT, ()))
    assert [b.name for b in model.uml_boundaries] == ["Aggregate: Book"], (
        "a file whose t_diagramobjects has no rectangle columns reads"
    )
    assert TABLE_COLUMNS["t_diagramobjects"] == ("Diagram_ID", "Object_ID"), (
        "the required columns of t_diagramobjects are the diagram and the object"
    )


def _boundary_in_the_subtree(builder, ids):
    return builder.boundary(diagram=1, package=ids["library"], name="Aggregate: Book")


def _boundary_in_no_package(builder, ids):
    return builder.boundary(diagram=1, name="Aggregate: Book")


def _boundary_in_a_package_outside(builder, ids):
    return builder.boundary(diagram=1, package=ids["other"], name="Aggregate: Book")


def _boundary_with_a_stereotype(builder, ids):
    return builder.boundary(diagram=1, package=ids["library"], stereotype="legend")


@pytest.mark.parametrize(
    ("draw", "listed"),
    [
        (_boundary_in_the_subtree, True),
        (_boundary_in_a_package_outside, False),
        (_boundary_in_no_package, False),
        (_boundary_with_a_stereotype, False),
    ],
)
def test_a_boundary_of_a_converted_package_is_read_by_name_and_package(tmp_path, draw, listed):
    builder, ids = build_library(tmp_path)
    drawn = draw(builder, ids)
    found = as_model(read(builder)).uml_boundaries or []
    assert [(b.object_id, b.name, b.package_id, b.diagram_id) for b in found] == (
        [(drawn, "Aggregate: Book", ids["library"], 1)] if listed else []
    ), f"{draw.__name__}: listed {listed}"


# --- state machines: states, the initial node, StateFlows, Statechart diagrams (PD-1, PD-2) -----

INITIAL_NTYPE = 3


def build_loan(tmp_path: Path) -> tuple[QeaBuilder, dict[str, int]]:
    """The library with a Statechart ``loan``: Initial, two States, two StateFlows."""
    builder, ids = build_library(tmp_path)
    lib = ids["library"]
    ids["start"] = builder.state(lib, "Start", ntype=INITIAL_NTYPE)
    ids["requested"] = builder.state(lib, "requested", note="Asked for.")
    ids["approved"] = builder.state(lib, "approved")
    ids["first"] = builder.state_flow(ids["start"], ids["requested"])
    ids["second"] = builder.state_flow(
        ids["requested"], ids["approved"], tags={"roles": "librarian", "comment_required": "true"}
    )
    ids["chart"] = builder.statechart(
        "loan", lib, [ids["start"], ids["requested"], ids["approved"]]
    )
    return builder, ids


def test_a_statechart_reads_into_one_chart_with_its_nodes_and_flows(tmp_path):
    builder, ids = build_loan(tmp_path)
    model = as_model(read(builder))
    (chart,) = model.uml_statecharts
    assert (chart.diagram_id, chart.uml_name, chart.package_path) == (
        ids["chart"],
        "loan",
        ROOT,
    ), "the diagram is one record, named and placed"
    assert chart.node_ids == sorted([ids["start"], ids["requested"], ids["approved"]]), (
        "its nodes are the state nodes placed on it, by id"
    )
    nodes = {n.uml_name: (n.object_id, n.node_kind, n.note) for n in model.uml_state_nodes}
    assert nodes == {
        "Start": (ids["start"], "initial", None),
        "requested": (ids["requested"], "state", "Asked for."),
        "approved": (ids["approved"], "state", None),
    }, "the Initial StateNode is initial, a State is a state, the note is copied"
    flows = [(f.connector_id, f.source_id, f.target_id) for f in model.uml_state_flows]
    assert flows == [
        (ids["first"], ids["start"], ids["requested"]),
        (ids["second"], ids["requested"], ids["approved"]),
    ], "each StateFlow between two nodes of the subtree is one record, by connector id"
    assert [
        (t.owner_id, t.name, t.tag_value) for t in model.uml_state_flows[1].uml_tagged_values
    ] == [
        (ids["second"], "comment_required", "true"),
        (ids["second"], "roles", "librarian"),
    ], "its tags come from t_connectortag, sorted by name"
    assert not model.uml_state_flows[0].uml_tagged_values, "the Initial flow has no tags"


def test_state_machine_rows_leave_the_classes_and_links_as_they_were(tmp_path):
    builder, _ = build_loan(tmp_path)
    model = as_model(read(builder))
    assert names(model) == ["lib:Book", "lib:Chapter", "lib:Folio", "lib:Genre"], names(model)
    assert not model.uml_links, "a StateFlow is no link"


def test_a_model_with_no_state_machine_reads_no_state_records(tmp_path):
    builder, _ = build_library(tmp_path)
    model = as_model(read(builder))
    assert (
        model.uml_state_nodes in (None, []),
        model.uml_state_flows in (None, []),
        model.uml_statecharts in (None, []),
    ) == (True, True, True), "nothing drawn, nothing read"


def test_a_diagram_that_is_not_a_statechart_is_not_read(tmp_path):
    builder, ids = build_loan(tmp_path)
    builder.diagram("class view", ids["library"], "Logical", [ids["book"]])
    assert len(as_model(read(builder)).uml_statecharts) == 1, "only the Statechart is read"


def test_a_statechart_outside_the_subtree_is_not_read(tmp_path):
    builder, ids = build_library(tmp_path)
    away = builder.state(ids["other"], "away")
    builder.statechart("elsewhere", ids["other"], [away])
    model = as_model(read(builder))
    assert model.uml_statecharts in (None, []), "a diagram in another package is not read"
    assert model.uml_state_nodes in (None, []), "nor are its states"


def test_an_empty_statechart_in_a_converted_package_is_not_read(tmp_path):
    builder, ids = build_loan(tmp_path)
    builder.statechart("placeholder", ids["library"], [])
    model = as_model(read(builder))
    assert [chart.uml_name for chart in model.uml_statecharts] == ["loan"], (
        "a diagram that shows no converted state node is no workflow, wherever it sits (C2)"
    )


def test_a_statechart_in_an_excluded_package_showing_converted_states_is_read(tmp_path):
    builder, ids = build_library(tmp_path)
    start = builder.state(ids["library"], "Start", ntype=INITIAL_NTYPE)
    requested = builder.state(ids["library"], "requested")
    builder.state_flow(start, requested)
    chart = builder.statechart("loan", ids["rare"], [start, requested])
    model = as_model(read(builder, excluded=(f"{ROOT}/rare-books",)))
    (found,) = model.uml_statecharts
    assert (found.diagram_id, found.package_path, found.node_ids) == (
        chart,
        f"{ROOT}/rare-books",
        sorted([start, requested]),
    ), "the diagram is selected by the converted nodes it shows, not by its package (C2)"


def test_a_statechart_in_a_sibling_package_showing_converted_states_is_read(tmp_path):
    builder, ids = build_library(tmp_path)
    requested = builder.state(ids["library"], "requested")
    chart = builder.statechart("loan", ids["other"], [requested])
    (found,) = as_model(read(builder)).uml_statecharts
    assert (found.diagram_id, found.package_path) == (chart, "MODEL/other"), (
        "a diagram outside the converted packages is read when it shows a converted state (C2)"
    )


def test_a_state_node_of_another_kind_is_still_read_with_its_type(tmp_path):
    builder, ids = build_library(tmp_path)
    final = builder.state(ids["library"], "End", ntype=4)
    (node,) = as_model(read(builder)).uml_state_nodes
    assert (node.object_id, node.node_kind, node.node_type) == (final, None, 4), (
        "the reader copies the NType and judges nothing: the workflow rule does (PD-5)"
    )


def test_a_state_flow_with_one_end_outside_the_subtree_is_a_no_rule_problem(tmp_path):
    builder, ids = build_loan(tmp_path)
    away = builder.state(ids["other"], "away")
    builder.state_flow(ids["approved"], away)
    assert as_problems(read(builder)) == [
        "[no_rule] approved -> away: StateFlow crossing the converted packages: no rule converts it"
    ], "a StateFlow leaving the subtree is a problem naming its ends"


def test_a_state_flow_between_two_outside_states_is_not_read(tmp_path):
    builder, ids = build_loan(tmp_path)
    left, right = builder.state(ids["other"], "left"), builder.state(ids["other"], "right")
    builder.state_flow(left, right)
    assert len(as_model(read(builder)).uml_state_flows) == 2, "a flow away from the subtree is not"


def test_a_substate_is_a_no_rule_problem(tmp_path):
    builder, ids = build_loan(tmp_path)
    builder.state(ids["library"], "inner", parent=ids["requested"])
    assert as_problems(read(builder)) == ["[no_rule] inner: substate: no rule converts it"], (
        "a state with a ParentID is a problem naming it"
    )


def test_a_state_owning_operations_is_a_no_rule_problem(tmp_path):
    builder, ids = build_loan(tmp_path)
    builder.operation(ids["approved"], "entry")
    assert as_problems(read(builder)) == [
        "[no_rule] approved: State with entry, do or exit behaviour: no rule converts it"
    ], "a state that owns t_operation rows is a problem naming it"


@pytest.mark.parametrize(
    ("change", "what"),
    [
        ({"name": "go"}, "StateFlow with a name"),
        ({"pdata": {1: "x"}}, "StateFlow with PDATA1"),
        ({"pdata": {2: "x"}}, "StateFlow with PDATA2"),
        ({"pdata": {3: "x"}}, "StateFlow with PDATA3"),
        ({"pdata": {4: "x"}}, "StateFlow with PDATA4"),
        ({"pdata": {5: "x"}}, "StateFlow with PDATA5"),
        ({"stereotype": "signal"}, "StateFlow with a stereotype"),
        ({"trigger": True}, "StateFlow with a trigger"),
    ],
)
def test_a_state_flow_with_a_construct_the_converter_does_not_know_is_a_no_rule_problem(
    tmp_path, change, what
):
    builder, ids = build_loan(tmp_path)
    builder.state_flow(ids["approved"], ids["requested"], **change)
    assert as_problems(read(builder)) == [
        f"[no_rule] approved -> requested: {what}: no rule converts it"
    ], "the flow is refused, naming it and the construct"


def test_a_memo_connector_tag_takes_its_text_from_the_notes(tmp_path):
    builder, ids = build_library(tmp_path)
    first, second = builder.state(ids["library"], "a"), builder.state(ids["library"], "b")
    flow = builder.state_flow(first, second, memo_tags={"roles": "librarian,reader"})
    builder.statechart("memo", ids["library"], [first, second])
    (read_flow,) = as_model(read(builder)).uml_state_flows
    assert [(t.owner_id, t.name, t.tag_value) for t in read_flow.uml_tagged_values] == [
        (flow, "roles", "librarian,reader")
    ], "a <memo> value is read from NOTES, as for a class tag"


# --- diagrams: membership and hidden connectors, no geometry (PD-12, RISK-6) ----------------------


def build_shelf(tmp_path: Path) -> tuple[QeaBuilder, dict[str, int]]:
    """The library with one association Book -> Folio, which a diagram may show or hide."""
    builder, ids = build_library(tmp_path)
    ids["has_folio"] = builder.association(ids["book"], ids["folio"], "lib:hasFolio", "0..*")
    return builder, ids


def _row_hiding(builder, diagram, connector):
    builder.diagram_link(diagram, connector, hidden=True)


def _row_not_hiding(builder, diagram, connector):
    builder.diagram_link(diagram, connector, hidden=False)


def _row_of_another_diagram(builder, diagram, connector):
    other = builder.diagram("elsewhere", 0, "Logical", [])
    builder.diagram_link(other, connector, hidden=True)


def _no_row(builder, diagram, connector):
    return None


@pytest.mark.parametrize(
    ("write_row", "hidden"),
    [
        (_no_row, False),
        (_row_not_hiding, False),
        (_row_hiding, True),
        (_row_of_another_diagram, False),
    ],
)
def test_a_connector_is_hidden_only_by_a_row_of_its_own_diagram_that_says_so(
    tmp_path, write_row, hidden
):
    builder, ids = build_shelf(tmp_path)
    diagram = builder.diagram("shelf", ids["library"], "Logical", [ids["book"], ids["folio"]])
    write_row(builder, diagram, ids["has_folio"])
    (found,) = as_model(read(builder)).uml_diagrams
    assert list(found.hidden_connector_ids or []) == ([ids["has_folio"]] if hidden else []), (
        f"{write_row.__name__}: hidden {hidden}"
    )


def test_a_hidden_row_of_a_connector_with_an_end_off_the_diagram_is_not_kept(tmp_path):
    builder, ids = build_shelf(tmp_path)
    diagram = builder.diagram("shelf", ids["library"], "Logical", [ids["book"]])
    builder.diagram_link(diagram, ids["has_folio"], hidden=True)
    (found,) = as_model(read(builder)).uml_diagrams
    assert not found.hidden_connector_ids, "the connector is not shown anyway: nothing to hide"


def test_a_diagram_is_read_by_its_members_its_package_and_its_type(tmp_path):
    builder, ids = build_shelf(tmp_path)
    note = builder.cls(ids["library"], "a note", object_type="Note")
    diagram = builder.diagram("shelf", ids["library"], "Logical", [ids["folio"], ids["book"], note])
    boundary = builder.boundary(diagram, package=ids["library"], name="Aggregate: Book")
    (found,) = as_model(read(builder)).uml_diagrams
    assert (found.diagram_id, found.name, found.package_id, found.diagram_type) == (
        diagram,
        "shelf",
        ids["library"],
        "Logical",
    ), "the diagram is one record: its name, its package and its type as EA writes it"
    assert list(found.element_ids) == sorted([ids["book"], ids["folio"], boundary]), (
        "its members are the objects placed on it, by id; a note is furniture and is left out"
    )


@pytest.mark.parametrize(
    ("diagram_type", "package", "read_back"),
    [
        ("Logical", "library", True),
        ("Statechart", "library", False),
        ("Logical", "other", False),
    ],
)
def test_only_a_class_diagram_of_a_converted_package_is_read(
    tmp_path, diagram_type, package, read_back
):
    builder, ids = build_shelf(tmp_path)
    builder.diagram("d", ids[package], diagram_type, [ids["book"]])
    found = as_model(read(builder)).uml_diagrams or []
    assert bool(found) is read_back, f"{diagram_type} in {package}: read {read_back}"


@pytest.mark.parametrize(
    ("written", "read_back"), [("Holds.", "Holds."), (None, None), ("  ", None)]
)
def test_a_composition_carries_the_note_written_on_its_connector(tmp_path, written, read_back):
    builder, ids = build_library(tmp_path)
    builder.aggregation(ids["book"], ids["folio"], note=written)
    (found,) = as_model(read(builder)).uml_compositions
    assert found.note == read_back, f"note {written!r}"


def test_a_model_with_no_diagram_reads_no_diagram(tmp_path):
    builder, _ = build_shelf(tmp_path)
    assert not as_model(read(builder)).uml_diagrams, "nothing drawn, nothing read"


def test_the_diagram_tables_are_read_by_their_ids_only():
    assert TABLE_COLUMNS["t_diagramlinks"] == ("DiagramID", "ConnectorID", "Hidden"), (
        "no geometry, no style: membership and visibility only (PD-12)"
    )


def test_a_missing_diagram_links_table_is_named(tmp_path):
    builder, _ = build_shelf(tmp_path)
    path = builder.finish()
    _alter(path, "DROP TABLE t_diagramlinks")
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path} has no table t_diagramlinks", error.value.message
