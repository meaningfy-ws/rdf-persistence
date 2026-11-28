"""Converter-side cases the rule table does not hold: a link to a note or boundary, a dependency to an excluded enum.

Records are built as ``test_uml_rules.py`` builds them (the reader is not involved).
"""

from pathlib import Path

import pytest

from rdf_persistence_generation.generated.rp_generation import (
    UmlLinkKind,
    UmlModel,
    UmlPackage,
)
from rdf_persistence_generation.uml.qea import read_qea
from tests.generator.uml_model import (
    BOOK,
    CATALOGUE_PKG,
    GENRE,
    LIBRARY_PKG,
    MODEL_PKG,
    enumeration,
    klass,
    link,
    model,
    run,
)
from tests.generator.uml_qea import QeaBuilder


@pytest.mark.parametrize("object_type", ["Note", "Boundary"])
def test_a_link_the_reader_skipped_to_a_note_or_boundary_does_not_stop_the_conversion(
    tmp_path: Path, object_type: str
) -> None:
    builder = QeaBuilder(tmp_path / "library.qea")
    top = builder.package("model")
    library = builder.package("library", parent=top)
    book = builder.cls(library, "lib:Book", stereotype="root", note="A book.")
    ignored = builder.cls(library, "lib:Ignored", object_type=object_type)
    builder.association(book, ignored, role="lib:ignored", card="0..1")
    builder.dependency(book, ignored, role="lib:dep")
    read = read_qea(builder.finish(), "model", ())
    assert isinstance(read, UmlModel), f"the reader found problems: {read}"

    out = run(read)

    assert out.problems == [], out.problem_texts()
    slots = out.schemas["app_library"].slots
    assert "ignored" not in slots, f"no slot for the association: {sorted(slots)}"
    assert "dep" not in slots, f"no slot for the dependency: {sorted(slots)}"


def test_a_dependency_to_an_enumeration_in_an_excluded_package_makes_no_slot_and_a_report_line():
    uml = model(
        klass(BOOK, "lib:Book"),
        links=(link(1, BOOK, GENRE, kind=UmlLinkKind.DEPENDENCY, target_role="lib:genre"),),
        packages=(
            UmlPackage(package_id=MODEL_PKG, name="model"),
            UmlPackage(package_id=LIBRARY_PKG, name="library", parent_id=MODEL_PKG),
        ),
        outside=(enumeration(GENRE, "lib:Genre", ("fiction",), CATALOGUE_PKG),),
        outside_packages=(
            UmlPackage(package_id=CATALOGUE_PKG, name="catalogue", parent_id=MODEL_PKG),
        ),
    )

    out = run(uml, exclude_packages=["catalogue"])

    assert out.problems == [], out.problem_texts()
    assert "genre" not in out.schemas["app_library"].slots, "no slot is made"
    assert [line.split(":")[0] for line in out.report_lines("excluded_link")] == [
        "Book.genre -> Genre"
    ], out.report_lines("excluded_link")
