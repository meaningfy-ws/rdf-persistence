"""The generic library model of the stage-1 golden (TC-11) and IT-1, written as a ``.qea`` file.

A helper, not a test module. The model is ``MODEL/library`` with the packages ``catalogue`` and
``shelves``, plus ``MODEL/external`` that is not converted. It carries every stage-1 rule once: a root
with attributes, a part reached by a ``1..*`` association with a composition beside it, a root in another
package that the first one points at, an enumeration with literals and a dependency to it, an empty
enumeration, an abstract parent with a subclass, a not-generated class and a link to a class outside
the subtree. Most elements have a note, one has none. No stage-2 feature (toolkit slots, tagged
values, shared slots across packages) is drawn.
"""

from pathlib import Path

from tests.generator.uml_qea import QeaBuilder

PACKAGE = "MODEL/library"
ROOT_NAME = "library"
PREFIXES = """\
schema_base: https://example.org/ns/library/
default_prefix: lib
version: "1"
prefixes:
  lib: https://example.org/ns/library#
  dct: http://purl.org/dc/terms/
"""


def write_prefixes(folder: Path) -> Path:
    path = folder / "prefixes.yaml"
    path.write_text(PREFIXES, encoding="utf-8")
    return path


def _catalogue(builder: QeaBuilder, package: int, root: str | None) -> dict[str, int]:
    ids: dict[str, int] = {}
    ids["book"] = builder.cls(package, "lib:Book", stereotype=root, note="A book in the library.")
    ids["chapter"] = builder.cls(package, "lib:Chapter", note="A chapter of a book.")
    builder.attribute(
        ids["book"], "dct:title", "xsd:string", "1", "1", note="The title of the book."
    )
    builder.attribute(ids["book"], "lib:subtitle", "xsd:string", "0", "1", note="Its subtitle.")
    builder.attribute(
        ids["book"], "lib:pages", "xsd:nonNegativeInteger", "0", "1", note="Its page count."
    )
    builder.attribute(
        ids["chapter"], "lib:heading", "xsd:string", "1", "1", note="The heading of the chapter."
    )
    ids["genre"] = builder.cls(
        package, "lib:Genre", object_type="Enumeration", note="The kinds of book."
    )
    builder.attribute(ids["genre"], "lib:fiction", note="Invented stories.", pos=0)
    builder.attribute(ids["genre"], "lib:poetry", pos=1)  # the one element without a note
    ids["language"] = builder.cls(
        package, "lib:Language", object_type="Enumeration", note="The languages, kept outside."
    )
    ids["publication"] = builder.cls(
        package, "lib:Publication", abstract=True, note="Anything published."
    )
    builder.attribute(
        ids["publication"], "lib:issued", "xsd:date", "0", "1", note="When it was issued."
    )
    ids["periodical"] = builder.cls(
        package, "lib:Periodical", stereotype=root, note="A publication in issues."
    )
    builder.attribute(ids["periodical"], "lib:issn", "xsd:string", "0", "1", note="Its ISSN.")
    ids["authority"] = builder.cls(
        package, "lib:Authority", stereotype="loaded graph", note="A list loaded from elsewhere."
    )
    return ids


def _links(builder: QeaBuilder, ids: dict[str, int]) -> None:
    book = ids["book"]
    builder.association(
        book, ids["chapter"], "lib:hasChapter", "1..*", note="The chapters of the book."
    )
    builder.aggregation(book, ids["chapter"])  # the composition that owns the chapters (PD-1, PD-2)
    builder.association(
        book, ids["shelf"], "lib:shelvedOn", "0..1", note="The shelf the book stands on."
    )
    builder.association(
        book, ids["authority"], "lib:authority", "0..1", note="The authority that names it."
    )
    builder.association(
        book, ids["work"], "lib:relatedWork", "0..*", note="A work elsewhere it relates to."
    )
    builder.dependency(book, ids["genre"], "lib:genre", note="The kind of the book.")
    builder.dependency(book, ids["language"], "lib:language", note="The languages it is in.")
    builder.generalisation(ids["periodical"], ids["publication"])


def build_library(folder: Path, annotated: bool = True) -> Path:
    """Write ``library.qea`` into ``folder``; the package to convert is ``PACKAGE``.

    ``annotated=False`` draws the same model with no «root» and no boundary (compositions stay): the
    other drawing of the byte-identity claim (PD-6a).
    """
    root = "root" if annotated else None
    builder = QeaBuilder(folder / "library.qea")
    model = builder.package("MODEL")
    library = builder.package("library", parent=model, note="The library and its books.")
    catalogue = builder.package("catalogue", parent=library, note="What the library holds.")
    shelves = builder.package("shelves", parent=library, note="Where the books stand.")
    external = builder.package("external", parent=model)
    ids = _catalogue(builder, catalogue, root)
    ids["shelf"] = builder.cls(shelves, "lib:Shelf", stereotype=root, note="A shelf of books.")
    builder.attribute(ids["shelf"], "lib:location", "xsd:string", "1", "1", note="Where it is.")
    builder.tag(ids["shelf"], "rp_path", "shelves")  # the derived plural would be "shelfs"
    ids["work"] = builder.cls(external, "ext:Work", note="A work in another model.")
    _links(builder, ids)
    # a boundary is an annotation, named for its root and kept in the root's converted package (PD-7)
    if annotated:
        builder.boundary(diagram=1, package=catalogue, name="Book")
    return builder.finish()
