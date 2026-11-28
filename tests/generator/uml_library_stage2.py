"""The generic library model of the stage-2 golden (TC-11) and IT-1, written as a ``.qea`` file.

A helper, not a test module. It is the worked example of the design (``Book`` with ``rp_mixins=StoredFile``
and a unique key, ``dct:identifier``, a ``1..*`` part ``Chapter`` by a composition, ``shelvedOn`` to the root
``Shelf``) with what the extended model adds, each once: an activity root ``Loan``, a «tenant root» ``Library``, an
abstract root ``Work`` that its two roots specialise and that a slot ranges over, and a slot (``location``)
used in two packages, so it is defined once in the package the other imports. Every element has a note.
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
  prov: http://www.w3.org/ns/prov#
"""


def write_prefixes(folder: Path) -> Path:
    path = folder / "prefixes.yaml"
    path.write_text(PREFIXES, encoding="utf-8")
    return path


def _catalogue(builder: QeaBuilder, package: int) -> dict[str, int]:
    ids: dict[str, int] = {}
    ids["work"] = builder.cls(
        package, "lib:Work", abstract=True, note="Anything the library holds."
    )
    ids["book"] = builder.cls(
        package, "lib:Book", stereotype="root", note="A book held by the library."
    )
    ids["periodical"] = builder.cls(
        package, "lib:Periodical", stereotype="root", note="A publication in issues."
    )
    ids["chapter"] = builder.cls(package, "lib:Chapter", note="A chapter of a book.")
    builder.tag(ids["book"], "rp_mixins", "StoredFile")
    builder.tag(ids["book"], "unique_key", "title_subtitle: title, subtitle")
    builder.tag(ids["chapter"], "rp_unlabelled", "true")
    builder.attribute(
        ids["book"], "dct:title", "xsd:string", "1", "1", note="The title of the book.", pos=0
    )
    builder.attribute(
        ids["book"], "lib:subtitle", "xsd:string", "0", "1", note="Its subtitle.", pos=1
    )
    builder.attribute(
        ids["book"], "dct:identifier", "xsd:string", "1", "1", note="Its catalogue number.", pos=2
    )
    builder.attribute(
        ids["book"], "lib:location", "xsd:string", "0", "1", note="Where it is.", pos=3
    )
    builder.attribute(ids["periodical"], "lib:issn", "xsd:string", "0", "1", note="Its ISSN.")
    builder.attribute(ids["chapter"], "lib:heading", "xsd:string", "1", "1", note="The heading.")
    return ids


def _shelves(builder: QeaBuilder, package: int) -> dict[str, int]:
    ids: dict[str, int] = {}
    ids["shelf"] = builder.cls(package, "lib:Shelf", stereotype="root", note="A shelf of books.")
    builder.tag(ids["shelf"], "rp_path", "shelves")  # the derived plural would be "shelfs"
    builder.attribute(ids["shelf"], "lib:location", "xsd:string", "1", "1", note="Where it stands.")
    ids["library"] = builder.cls(
        package, "lib:Library", stereotype="tenant root", note="The library itself, the tenant."
    )
    builder.attribute(ids["library"], "lib:city", "xsd:string", "0", "1", note="Its city.")
    return ids


def _circulation(builder: QeaBuilder, package: int) -> dict[str, int]:
    loan = builder.cls(package, "lib:Loan", stereotype="root", note="A book lent to a reader.")
    builder.tag(loan, "rp_mixins", "Activity")
    builder.tag(loan, "rp_path", "loans")
    builder.attribute(
        loan, "prov:startedAtTime", "xsd:dateTime", "1", "1", note="When the loan started."
    )
    return {"loan": loan}


def _links(builder: QeaBuilder, ids: dict[str, int]) -> None:
    book = ids["book"]
    builder.generalisation(book, ids["work"])
    builder.generalisation(ids["periodical"], ids["work"])
    builder.association(
        book, ids["chapter"], "lib:hasChapter", "1..*", note="The chapters of the book."
    )
    builder.aggregation(book, ids["chapter"])  # the composition that owns the chapters (PD-1, PD-2)
    builder.association(
        book, ids["shelf"], "lib:shelvedOn", "0..1", note="The shelf the book stands on."
    )
    builder.association(book, ids["work"], "lib:relatedWork", "0..*", note="A work it relates to.")
    builder.association(ids["loan"], book, "lib:loanedBook", "1..1", note="The book that is lent.")


def build_library(folder: Path) -> Path:
    """Write ``library.qea`` into ``folder``; the package to convert is ``PACKAGE``."""
    builder = QeaBuilder(folder / "library.qea")
    model = builder.package("MODEL")
    library = builder.package("library", parent=model, note="The library and its books.")
    catalogue = builder.package("catalogue", parent=library, note="What the library holds.")
    shelves = builder.package("shelves", parent=library, note="Where the books stand.")
    circulation = builder.package("circulation", parent=library, note="Who has which book.")
    ids = _catalogue(builder, catalogue)
    ids |= _shelves(builder, shelves)
    ids |= _circulation(builder, circulation)
    _links(builder, ids)
    # a boundary is an annotation, named for its root and kept in the root's converted package (PD-7)
    builder.boundary(diagram=1, package=catalogue, name="Book")
    return builder.finish()
