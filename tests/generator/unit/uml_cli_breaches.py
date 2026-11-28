"""The eleven breaches of PD-13 and D-14: each seeds a clean noted library with exactly one.

A seed takes the builder and the ids ``noted_library`` returns (``book``, ``chapter``, ``folio``,
``library``) and adds the one thing a convention or a rule refuses. Every added element carries a
note and a prefix, so nothing else is reported.
"""

from collections.abc import Callable

from tests.generator.uml_qea import QeaBuilder

Ids = dict[str, int]
Seed = Callable[[QeaBuilder, Ids], None]

TOOLKIT_PREFIX = "  rp: https://meaningfy.ws/ns/rdf-persistence#\n"
NOTE = "A note."


def _compose(builder: QeaBuilder, ids: Ids) -> None:
    """The book holds the chapter: a composition and the association that names its role."""
    builder.association(ids["book"], ids["chapter"], "lib:hasChapter", "0..*", note=NOTE)
    builder.aggregation(ids["book"], ids["chapter"])  # one candidate association: no role needed


def unprefixed_class(builder: QeaBuilder, ids: Ids) -> None:
    builder.cls(ids["library"], "Shelf", note=NOTE)


def no_multiplicity(builder: QeaBuilder, ids: Ids) -> None:
    builder.association(ids["book"], ids["folio"], "lib:hasFolio", None, note=NOTE)


def no_note(builder: QeaBuilder, ids: Ids) -> None:
    builder.cls(ids["library"], "lib:Shelf")


def part_drawn_root(builder: QeaBuilder, ids: Ids) -> None:
    _compose(builder, ids)  # the chapter is a part, and the library draws it «root»


def unused_enumeration(builder: QeaBuilder, ids: Ids) -> None:
    genre = builder.cls(ids["library"], "lib:Genre", object_type="Enumeration", note=NOTE)
    builder.attribute(genre, "lib:fiction", note=NOTE)  # a literal; with none the list is external


def two_packages_one_module(builder: QeaBuilder, ids: Ids) -> None:
    for package_name, class_name in (("rare-books", "lib:Atlas"), ("rare_books", "lib:Codex")):
        package = builder.package(package_name, parent=ids["library"])
        builder.cls(package, class_name, note=NOTE)


def role_owned_and_pointer(builder: QeaBuilder, ids: Ids) -> None:
    _compose(builder, ids)
    builder.association(ids["folio"], ids["book"], "lib:hasChapter", "1", note=NOTE)


def pointer_into_a_part(builder: QeaBuilder, ids: Ids) -> None:
    _compose(builder, ids)
    builder.association(ids["folio"], ids["chapter"], "lib:cites", "0..1", note=NOTE)


def drawn_toolkit_parent(builder: QeaBuilder, ids: Ids) -> None:
    described = builder.cls(ids["library"], "rp:Described")
    builder.generalisation(ids["book"], described)


def tenant_required_pointer(builder: QeaBuilder, ids: Ids) -> None:
    tenant = builder.cls(ids["library"], "lib:Library", stereotype="tenant root", note=NOTE)
    builder.association(tenant, ids["book"], "lib:holds", "1", note=NOTE)


def boundary_for_a_part(builder: QeaBuilder, ids: Ids) -> None:
    _compose(builder, ids)
    diagram = builder.diagram("library", ids["library"], "Logical", [])
    builder.boundary(diagram, ids["library"], name="Aggregate: Chapter")
