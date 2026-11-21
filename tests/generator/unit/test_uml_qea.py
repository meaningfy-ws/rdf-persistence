"""The .qea reader (PD-3, PD-4): the subtree, the usage errors, the tagged values, the boundaries."""

import sqlite3
from pathlib import Path

import pytest

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    UmlLinkKind,
    UmlModel,
    UmlRule,
)
from rdf_persistence_generation.problems import format_problem
from rdf_persistence_generation.uml.qea import QeaUsageError, read_qea
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


def test_a_missing_file_is_not_an_ea_file(tmp_path):
    path = tmp_path / "absent.qea"
    with pytest.raises(QeaUsageError) as error:
        read_qea(path, ROOT, ())
    assert error.value.message == f"{path} is not an Enterprise Architect .qea (SQLite) file", (
        error.value.message
    )


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


# --- TC-2: boundary membership by geometry -----------------------------------------------------

BOX = (-20, 30, 320, -298)  # (left, top, right, bottom); y grows upwards, so top > bottom
INSIDE = (0, 0, 100, -50)
ON_THE_EDGE = (-20, 30, 100, -50)
STRADDLING = (300, 0, 400, -50)
OUTSIDE = (500, 0, 600, -50)


def boundary_world(tmp_path: Path) -> tuple[QeaBuilder, dict[str, int]]:
    builder, ids = build_library(tmp_path)
    ids["box"] = builder.boundary(diagram=1, rect=BOX, members=[])
    return builder, ids


def members(model: UmlModel) -> list[tuple[int, list[int]]]:
    return [(b.diagram_id, sorted(b.member_ids)) for b in model.uml_boundaries]


def test_classes_inside_or_on_the_edge_are_members_and_outside_ones_are_not(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(1, ids["book"], INSIDE)
    builder.place(1, ids["chapter"], ON_THE_EDGE)
    builder.place(1, ids["genre"], OUTSIDE)
    model = as_model(read(builder))
    assert members(model) == [(1, sorted([ids["book"], ids["chapter"]]))], (
        "inside and on the edge are members, outside is not"
    )
    assert model.uml_boundaries[0].object_id == ids["box"], "the boundary is the box"


def test_the_rectangles_are_normalised_whichever_way_they_are_written(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(1, ids["book"], (100, -50, 0, 0))  # left > right, top < bottom
    builder.place(1, ids["chapter"], (310, -290, 320, -298))  # on the corner
    assert members(as_model(read(builder))) == [(1, sorted([ids["book"], ids["chapter"]]))], (
        "a rectangle written the other way round is normalised"
    )


def test_a_boundary_written_the_other_way_up_still_holds_its_members(tmp_path):
    builder, ids = build_library(tmp_path)
    builder.boundary(diagram=1, rect=(-20, -298, 320, 30), members=[])  # top < bottom
    builder.place(1, ids["book"], INSIDE)
    assert members(as_model(read(builder))) == [(1, [ids["book"]])], "Book is a member"


def test_a_class_that_straddles_a_boundary_is_a_no_rule_problem(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(1, ids["book"], INSIDE)
    builder.place(1, ids["chapter"], STRADDLING)
    assert as_problems(read(builder)) == [
        "[no_rule] lib:Chapter: straddles boundary Boundary: no rule converts it"
    ], "a class half in the boundary is a problem"


def test_a_class_placed_twice_inside_and_outside_is_a_no_rule_problem(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(1, ids["book"], INSIDE)
    builder.place(1, ids["book"], OUTSIDE)
    assert as_problems(read(builder)) == [
        "[no_rule] lib:Book: placed twice on the diagram of boundary Boundary, "
        "inside and outside: no rule converts it"
    ], "a class placed both inside and outside is a problem"


def test_a_class_placed_twice_inside_is_still_one_member(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(1, ids["book"], INSIDE)
    builder.place(1, ids["book"], ON_THE_EDGE)
    assert members(as_model(read(builder))) == [(1, [ids["book"]])], "Book is one member"


def test_a_class_inside_two_boundaries_is_a_no_rule_problem(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.boundary(diagram=2, rect=BOX, members=[])
    builder.place(1, ids["book"], INSIDE)
    builder.place(2, ids["book"], INSIDE)
    assert as_problems(read(builder)) == [
        "[no_rule] lib:Book: inside two boundaries: no rule converts it"
    ], "a class in two boundaries is a problem"


def test_a_boundary_on_two_diagrams_with_equal_members_is_one_boundary(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(2, ids["box"], BOX)
    builder.place(1, ids["book"], INSIDE)
    builder.place(2, ids["book"], INSIDE)
    model = as_model(read(builder))
    assert members(model) == [(1, [ids["book"]])], "the two diagrams give one boundary"


def test_a_boundary_on_two_diagrams_with_unequal_members_is_a_no_rule_problem(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(2, ids["box"], BOX)
    builder.place(1, ids["book"], INSIDE)
    builder.place(2, ids["chapter"], INSIDE)
    assert as_problems(read(builder)) == [
        "[no_rule] Boundary: members differ between diagrams 1 and 2: no rule converts it"
    ], "a boundary whose diagrams disagree is a problem"


def test_a_boundary_with_a_stereotype_is_ignored(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.cls(ids["library"], "Legend", stereotype="legend", object_type="Boundary")
    builder.place(1, ids["book"], INSIDE)
    assert members(as_model(read(builder))) == [(1, [ids["book"]])], "the legend is no boundary"


def test_a_boundary_holding_no_converted_class_is_left_out(tmp_path):
    builder, ids = boundary_world(tmp_path)
    builder.place(1, ids["stray"], INSIDE)
    assert as_model(read(builder)).uml_boundaries == [], "a boundary with no converted class goes"
