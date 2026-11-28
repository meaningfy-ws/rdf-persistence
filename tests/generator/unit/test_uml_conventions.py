"""The conventions pass (PD-13, PD-15, PD-19, PD-20): lines that are no problem and fail ``--check``.

``missing_notes`` and ``convention_lines`` are called with hand-built records and no ``Context``. A
convention row passes when the pass returns the line the design's error matrix gives for its drawing,
and fails (no line) for the near miss beside it. The library domain is ``lib:`` throughout.
"""

import pytest
from linkml_runtime.linkml_model import SlotDefinition

from rdf_persistence_generation.generated.rp_generation import (
    ReportKind,
    UmlAggregates,
    UmlBoundary,
    UmlClass,
    UmlDiagram,
    UmlElement,
    UmlLink,
    UmlLinkKind,
    UmlName,
    UmlObject,
    UmlReach,
)
from rdf_persistence_generation.uml.conventions import (
    CONVENTION_KINDS,
    convention_lines,
    missing_notes,
)
from rdf_persistence_generation.uml.naming import local_of
from rdf_persistence_generation.uml.slots import (
    FROM_ATTRIBUTE,
    FROM_LINK,
    OWNED,
    Usage,
    parse_bounds,
    shape_of,
)
from tests.generator.uml_model import (
    BOOK,
    CHAPTER,
    GENRE,
    LIBRARY_PKG,
    SHELF,
    attribute,
    composition,
    enumeration,
    generalisation,
    klass,
    link,
    model,
    run,
    tag,
)

NO_NOTE = "no note, so no description"


# --- PD-20: "no note" has one home; its text is what the converter wrote before the move --------------


def _noteless_model():
    """A noteless class, literal, attribute, role, dependency and a toolkit-slot attribute."""
    genre = klass(
        GENRE,
        "lib:Genre",
        object_type="Enumeration",
        attributes=(attribute(1, GENRE, "fiction", "", note=None),),
    )
    book = klass(
        BOOK,
        "lib:Book",
        note=None,
        attributes=(
            attribute(2, BOOK, "lib:pages", "xsd:integer", note=None),
            attribute(3, BOOK, "prov:startedAtTime", "xsd:dateTime", note=None),
        ),
    )
    return model(
        book,
        klass(SHELF, "lib:Shelf"),
        genre,
        links=(
            link(1, BOOK, SHELF, target_role="lib:shelf", note=None),
            link(2, BOOK, GENRE, kind=UmlLinkKind.DEPENDENCY, target_role="lib:genre", note=None),
        ),
    )


NOTELESS = [
    ("a class", "Book"),
    ("an enumeration literal", "Genre.fiction"),
    ("an attribute", "Book.pages"),
    ("a role", "Book.shelf"),
    ("an enumeration dependency", "Book.genre"),
    ("an attribute that becomes a toolkit slot (A-19)", "Book.startedAtTime"),
]


def test_each_noteless_element_has_one_no_note_line_with_todays_text():
    out = run(_noteless_model())
    assert out.problems == [], out.problem_texts()
    assert sorted(out.report_lines("no_note")) == sorted(
        f"{name}: {NO_NOTE}" for _, name in NOTELESS
    ), "one line for each of: " + ", ".join(what for what, _ in NOTELESS)


def test_a_noted_element_has_no_no_note_line():
    out = run(model(klass(BOOK, "lib:Book"), klass(SHELF, "lib:Shelf")))
    assert out.report_lines("no_note") == [], "the note is the description, nothing is missing"


def _element(uml: UmlClass) -> UmlElement:
    label = local_of(uml.name)
    return UmlElement(
        uml_class=uml,
        resolved_name=UmlName(name=label),
        label=label,
        module_path=[],
        is_enum=uml.object_type == "Enumeration",
    )


def _usage(holder: UmlElement, written: str, slot: str, note: str | None, origin: int) -> Usage:
    """A slot as the slot passes make it: its description is the note, or nothing when none."""
    shape = shape_of(slot, ("string", note), parse_bounds("1..1"))
    identity = SlotDefinition(name=slot)
    return Usage(holder, (identity, UmlName(name=written)), (origin, 0, slot), shape)


BOOK_ELEMENT = _element(klass(BOOK, "lib:Book"))
NOTELESS_BOOK = _element(klass(BOOK, "lib:Book", note=None))
NOTELESS_GENRE = _element(
    klass(
        GENRE,
        "lib:Genre",
        object_type="Enumeration",
        attributes=(
            attribute(1, GENRE, "fiction", "", note=None),
            attribute(2, GENRE, "poetry", "", note="Verse."),
        ),
    )
)
MISSING_NOTE_ROWS = [
    ("a noteless class", [NOTELESS_BOOK], [], [], ["Book"]),
    ("a noted class", [BOOK_ELEMENT], [], [], []),
    (
        "a noteless enumeration literal, not its noted sibling",
        [NOTELESS_GENRE],
        [],
        [],
        ["Genre.fiction"],
    ),
    (
        "a noteless attribute is named by its written local name",
        [BOOK_ELEMENT],
        [_usage(BOOK_ELEMENT, "pages", "page_count", None, FROM_ATTRIBUTE)],
        [],
        ["Book.pages"],
    ),
    (
        "a noteless role is named by its slot",
        [BOOK_ELEMENT],
        [_usage(BOOK_ELEMENT, "hasShelf", "shelf", None, FROM_LINK)],
        [],
        ["Book.shelf"],
    ),
    (
        "a noteless attribute that becomes a toolkit slot (A-19)",
        [BOOK_ELEMENT],
        [],
        [_usage(BOOK_ELEMENT, "startedAtTime", "started_at_time", None, FROM_ATTRIBUTE)],
        ["Book.startedAtTime"],
    ),
    (
        "a noted attribute and a noted toolkit slot",
        [BOOK_ELEMENT],
        [_usage(BOOK_ELEMENT, "pages", "pages", "The pages.", FROM_ATTRIBUTE)],
        [_usage(BOOK_ELEMENT, "startedAtTime", "started_at_time", "When.", FROM_ATTRIBUTE)],
        [],
    ),
]


@pytest.mark.parametrize(
    ("what", "elements", "usages", "toolkit_usages", "named"),
    MISSING_NOTE_ROWS,
    ids=[row[0] for row in MISSING_NOTE_ROWS],
)
def test_missing_notes_names_each_element_without_a_note(
    what, elements, usages, toolkit_usages, named
):
    found = missing_notes(elements, usages, toolkit_usages)
    assert [(line.report_kind, line.element, line.message) for line in found] == [
        (ReportKind.NO_NOTE, name, NO_NOTE) for name in named
    ], f"{what}: the lines are today's, one per element, with today's text"


# --- PD-12: diagrams are read by membership; two diagram kinds ---------------------------------------

DRAWN_BOUNDARY = 90
LIBRARY_ELEMENTS = [
    _element(klass(BOOK, "lib:Book")),
    _element(klass(CHAPTER, "lib:Chapter")),
    _element(klass(SHELF, "lib:Shelf")),
    _element(enumeration(GENRE, "lib:Genre", ("fiction",))),
]
COMPOSITION, ASSOCIATION, GENERALISATION = 1, 2, 3
CONNECTORS = {
    "compositions": (composition(COMPOSITION, BOOK, CHAPTER),),
    "links": (
        link(ASSOCIATION, BOOK, SHELF, target_role="lib:shelf"),
        generalisation(GENERALISATION, CHAPTER, BOOK),
    ),
}
EVERYTHING = [BOOK, CHAPTER, SHELF]


def _diagram(
    name: str,
    members: list[int],
    *,
    hidden: tuple[int, ...] = (),
    diagram_type: str = "Logical",
    package: int = LIBRARY_PKG,
) -> UmlDiagram:
    return UmlDiagram(
        diagram_id=1,
        name=name,
        package_id=package,
        diagram_type=diagram_type,
        element_ids=members,
        hidden_connector_ids=list(hidden),
    )


def _convention_lines(
    *diagrams: UmlDiagram,
    boundaries: tuple[UmlBoundary, ...] = (),
    objects: tuple[UmlObject, ...] = (),
    elements: list[UmlElement] | None = None,
    aggregates: UmlAggregates | None = None,
    usages: list[Usage] | None = None,
    drawn_toolkit: dict[int, str] | None = None,
    **drawing: tuple,
) -> list[str]:
    """``kind: element: message`` of every convention line; only records go in, no ``Context``."""
    used = elements or LIBRARY_ELEMENTS
    uml = model(
        *[each.uml_class for each in used],
        boundaries=boundaries,
        objects=objects,
        **{**CONNECTORS, **drawing},
    )
    uml.uml_diagrams = list(diagrams)
    found = convention_lines(
        uml, used, aggregates or UmlAggregates(), usages or [], drawn_toolkit or {}
    )
    return [
        f"{ReportKind(line.report_kind).value}: {line.element}: {line.message}" for line in found
    ]


def _of(kind: str, found: list[str]) -> list[str]:
    return [line for line in found if line.startswith(f"{kind}: ")]


AGGREGATES = "library · aggregates"
DIAGRAM_ROWS = [
    (
        "an aggregates diagram with compositions and generalisations only",
        _diagram(AGGREGATES, EVERYTHING, hidden=(ASSOCIATION,)),
        [],
    ),
    (
        "an aggregates diagram that shows an association",
        _diagram(AGGREGATES, EVERYTHING),
        [f"aggregates_diagram: {AGGREGATES}: shows the association Book.shelf"],
    ),
    (
        "an aggregates diagram where one end of the association is off the diagram",
        _diagram(AGGREGATES, [BOOK, CHAPTER]),
        [],
    ),
    (
        "an aggregates diagram that shows an enumeration",
        _diagram(AGGREGATES, [BOOK, GENRE]),
        [f"aggregates_diagram: {AGGREGATES}: shows the enumeration Genre"],
    ),
    (
        "an aggregates diagram that shows a boundary (A-18)",
        _diagram(AGGREGATES, [BOOK, DRAWN_BOUNDARY]),
        [],
    ),
    (
        "a diagram ending in the suffix whose prefix is not its package",
        _diagram("catalogue · aggregates", [BOOK]),
        [
            "aggregates_diagram: catalogue · aggregates: "
            "starts with catalogue, not the package name library"
        ],
    ),
    (
        "a diagram without the suffix is never read as an aggregates diagram",
        _diagram("library aggregates", [BOOK, SHELF, GENRE]),
        [],
    ),
    (
        "a diagram with the suffix in another spelling is none either",
        _diagram("library - aggregates", [BOOK, SHELF, GENRE]),
        [],
    ),
]


@pytest.mark.parametrize(
    ("what", "diagram", "expected"), DIAGRAM_ROWS, ids=[row[0] for row in DIAGRAM_ROWS]
)
def test_an_aggregates_diagram_shows_compositions_and_generalisations_only(what, diagram, expected):
    drawn = (UmlBoundary(object_id=DRAWN_BOUNDARY, name="Aggregate: Book", diagram_id=1),)
    found = _convention_lines(diagram, boundaries=drawn)
    assert _of("aggregates_diagram", found) == expected, what


def test_an_association_the_diagram_hides_is_not_shown():
    found = _convention_lines(_diagram(AGGREGATES, EVERYTHING, hidden=(ASSOCIATION,)))
    assert _of("aggregates_diagram", found) == [], "EA's own display rule: a Hidden row hides it"


COMPOSITION_ROWS = [
    (
        "a diagram that shows a composition",
        _diagram("library", [BOOK, CHAPTER]),
        ["composition_diagram: library: shows the composition Book → Chapter"],
    ),
    (
        "a diagram that hides the composition",
        _diagram("library", [BOOK, CHAPTER], hidden=(COMPOSITION,)),
        [],
    ),
    ("a diagram where the part is off the diagram", _diagram("library", [BOOK]), []),
    (
        "an aggregates diagram shows compositions by design",
        _diagram(AGGREGATES, [BOOK, CHAPTER]),
        [],
    ),
    (
        "a Statechart is ignored whatever it shows",
        _diagram("library", EVERYTHING, diagram_type="Statechart"),
        [],
    ),
]


@pytest.mark.parametrize(
    ("what", "diagram", "expected"), COMPOSITION_ROWS, ids=[row[0] for row in COMPOSITION_ROWS]
)
def test_any_other_class_diagram_does_not_show_a_composition(what, diagram, expected):
    found = _convention_lines(diagram)
    assert _of("composition_diagram", found) == expected, what


def test_a_statechart_gives_no_aggregates_line_whatever_its_name():
    found = _convention_lines(_diagram(AGGREGATES, EVERYTHING, diagram_type="Statechart"))
    assert _of("aggregates_diagram", found) == [], "a workflow is read apart (PD-12)"


def test_an_object_on_an_aggregates_diagram_is_named():
    drawn = UmlObject(object_id=70, uml_name="librarian", classifier_id=None)
    found = _convention_lines(_diagram(AGGREGATES, [BOOK, 70], hidden=()), objects=(drawn,))
    assert _of("aggregates_diagram", found) == [
        f"aggregates_diagram: {AGGREGATES}: shows the object librarian"
    ], "an element that is no class, note, text or boundary is named"


# --- PD-13: the eleven kinds that fail --check ----------------------------------------------------------


def test_the_convention_kinds_are_exactly_the_eleven_of_pd_13():
    assert {kind.value for kind in CONVENTION_KINDS} == {
        "boundary_disagrees",
        "composition_named",
        "aggregates_diagram",
        "composition_diagram",
        "unprefixed_name",
        "unused_enumeration",
        "drawn_toolkit_parent",
        "tenant_required_pointer",
        "no_note",
        "unspecified_multiplicity",
        "implicit_meaning",
    }, "the eleven kinds of PD-13, and no other"


@pytest.mark.parametrize("kind", ["deprecated_root", "toolkit_slot_kept", "root", "not_generated"])
def test_an_informational_kind_never_fails_the_check(kind):
    assert ReportKind(kind) not in CONVENTION_KINDS, f"{kind} is informational (PD-13, A-14)"


# --- C-1: unprefixed-name -------------------------------------------------------------------------------

PAGES = attribute(40, BOOK, "lib:pages", "xsd:integer")
BARE_PAGES = attribute(40, BOOK, "pages", "xsd:integer")


def _unprefixed(book: UmlClass, *links: UmlLink) -> list[str]:
    elements = [_element(book), _element(klass(SHELF, "lib:Shelf"))]
    return _of("unprefixed_name", _convention_lines(elements=elements, links=links))


UNPREFIXED_ROWS = [
    ("a prefixed class, attribute and role", klass(BOOK, "lib:Book", attributes=(PAGES,)), (), []),
    ("a class with no prefix", klass(BOOK, "Book"), (), ["unprefixed_name: Book: no prefix"]),
    (
        "an attribute with no prefix",
        klass(BOOK, "lib:Book", attributes=(BARE_PAGES,)),
        (),
        ["unprefixed_name: Book.pages: no prefix"],
    ),
    (
        "a role with no prefix",
        klass(BOOK, "lib:Book"),
        (link(5, BOOK, SHELF, target_role="shelf"),),
        ["unprefixed_name: Book.shelf: no prefix"],
    ),
    (
        "a prefixed role",
        klass(BOOK, "lib:Book"),
        (link(5, BOOK, SHELF, target_role="lib:shelf"),),
        [],
    ),
    (
        "a source role of a directed association gives no slot",
        klass(BOOK, "lib:Book"),
        (
            link(
                5,
                BOOK,
                SHELF,
                target_role="lib:shelf",
                source_role="owner",
                direction="Source -> Destination",
            ),
        ),
        [],
    ),
    (
        "a source role of a bi-directional association is the target class's slot",
        klass(BOOK, "lib:Book"),
        (link(5, BOOK, SHELF, target_role="lib:shelf", source_role="books"),),
        ["unprefixed_name: Shelf.books: no prefix"],
    ),
]


@pytest.mark.parametrize(
    ("what", "book", "links", "expected"), UNPREFIXED_ROWS, ids=[row[0] for row in UNPREFIXED_ROWS]
)
def test_a_class_an_attribute_or_a_role_is_written_with_a_prefix(what, book, links, expected):
    assert _unprefixed(book, *links) == expected, what


def test_an_enumeration_literal_with_no_prefix_keeps_its_own_line():
    genre = klass(
        GENRE,
        "lib:Genre",
        object_type="Enumeration",
        attributes=(attribute(1, GENRE, "fiction", "", note="Made up."),),
    )
    found = _convention_lines(elements=[_element(genre)])
    assert _of("unprefixed_name", found) == [], (
        "the literal is reported as implicit-meaning, not twice"
    )


# --- C-5: unused-enumeration ----------------------------------------------------------------------------


def _range_usage(holder: UmlElement, range_: str) -> Usage:
    shape = shape_of("genre", (range_, "A slot."), parse_bounds("0..1"))
    return Usage(
        holder,
        (SlotDefinition(name="genre"), UmlName(name="genre")),
        (FROM_LINK, 0, "genre"),
        shape,
    )


def test_an_enumeration_no_slot_ranges_over_is_reported():
    found = _convention_lines(usages=[])
    assert _of("unused_enumeration", found) == [
        "unused_enumeration: Genre: used by no dependency"
    ], "the enumeration is generated all the same, so it is a presentation finding"


def test_an_enumeration_a_slot_ranges_over_is_not_reported():
    book = LIBRARY_ELEMENTS[0]
    found = _convention_lines(usages=[_range_usage(book, "Genre")])
    assert _of("unused_enumeration", found) == [], "a dependency or an attribute uses it"


# --- C-11: drawn-toolkit-parent -------------------------------------------------------------------------

PARENT = 50


def _toolkit_parent(toolkit_class: str, *, classifying: bool) -> list[str]:
    drawn = (
        (UmlObject(object_id=70, uml_name="librarian", classifier_id=PARENT),)
        if classifying
        else ()
    )
    return _of(
        "drawn_toolkit_parent",
        _convention_lines(
            links=(generalisation(9, BOOK, PARENT),),
            objects=drawn,
            drawn_toolkit={PARENT: toolkit_class},
        ),
    )


def test_a_generalisation_to_a_drawn_toolkit_class_prefers_rp_mixins():
    assert _toolkit_parent("Described", classifying=False) == [
        "drawn_toolkit_parent: Book: prefer rp_mixins=Described"
    ], "the LinkML is the same either way; the tag is the convention (R-28)"


def test_a_drawn_role_definition_that_classifies_objects_is_not_a_parent():
    assert _toolkit_parent("RoleDefinition", classifying=True) == [], "the roles file's own type"


def test_a_drawn_role_definition_that_classifies_nothing_is_a_parent_like_any():
    assert _toolkit_parent("RoleDefinition", classifying=False) == [
        "drawn_toolkit_parent: Book: prefer rp_mixins=RoleDefinition"
    ], "only classifying Objects exempts it"


def test_a_generalisation_to_a_domain_class_is_no_toolkit_parent():
    found = _convention_lines(links=(generalisation(9, BOOK, CHAPTER),))
    assert _of("drawn_toolkit_parent", found) == [], "a domain parent is the model's own"


# --- C-12: tenant-required-pointer ----------------------------------------------------------------------

TENANT = BOOK


def _pointer(
    holder: int, *, required: bool = True, range_: str = "Shelf", owned: bool = False
) -> Usage:
    bounds = parse_bounds("1..1" if required else "0..1")
    marked = (OWNED,) if owned else ()
    shape = shape_of("shelf", (range_, "A slot."), bounds, marked=marked)
    holder_element = next(each for each in LIBRARY_ELEMENTS if each.uml_class.object_id == holder)
    return Usage(
        holder_element,
        (SlotDefinition(name="shelf"), UmlName(name="shelf")),
        (FROM_LINK, 0, "shelf"),
        shape,
    )


TENANT_AGGREGATES = UmlAggregates(
    tenant_root_id=TENANT,
    root_ids=[SHELF],
    reached_from=[UmlReach(part_id=CHAPTER, top_ids=[TENANT])],
)
TENANT_ROWS = [
    ("a required pointer from the tenant root to a root", _pointer(TENANT), True),
    ("a required pointer from a part of the tenant to a root", _pointer(CHAPTER), True),
    ("an optional pointer from the tenant root", _pointer(TENANT, required=False), False),
    (
        "a required pointer to a part of the tenant itself",
        _pointer(TENANT, range_="Chapter"),
        False,
    ),
    ("a required owned slot of the tenant root", _pointer(TENANT, owned=True), False),
    ("a required pointer from a class outside the tenant", _pointer(SHELF, range_="Book"), False),
]


@pytest.mark.parametrize(
    ("what", "usage", "reported"), TENANT_ROWS, ids=[row[0] for row in TENANT_ROWS]
)
def test_a_required_pointer_out_of_the_tenant_aggregate_cannot_be_set_at_creation(
    what, usage, reported
):
    found = _of(
        "tenant_required_pointer",
        _convention_lines(aggregates=TENANT_AGGREGATES, usages=[usage]),
    )
    expected = [
        f"tenant_required_pointer: {usage.holder.label}.shelf: "
        "required, cannot be set when the tenant is created"
    ]
    assert found == (expected if reported else []), what


# --- PD-7, D-1: boundary-disagrees; replaces the deleted two-roots test (A-23) ---------------------------

ROOTS = UmlAggregates(root_ids=[BOOK, SHELF])


def _boundary_lines(name: str, package: int | None = LIBRARY_PKG) -> list[str]:
    drawn = UmlBoundary(object_id=DRAWN_BOUNDARY, name=name, diagram_id=1, package_id=package)
    return _of("boundary_disagrees", _convention_lines(boundaries=(drawn,), aggregates=ROOTS))


BOUNDARY_ROWS = [
    ("a boundary named for a root", "Aggregate: Book", []),
    ("a boundary named for a root with no leading Aggregate", "Shelf", []),
    ("a boundary named for the written name of a root", "Aggregate: lib:Book", []),
    (
        "a boundary named for a class that is no root",
        "Aggregate: Chapter",
        ["boundary_disagrees: Aggregate: Chapter: names no root; a boundary is an annotation"],
    ),
    (
        "a boundary that names two roots (the two-roots drawing, now an annotation)",
        "Aggregate: Book, Shelf",
        ["boundary_disagrees: Aggregate: Book, Shelf: names no root; a boundary is an annotation"],
    ),
]


@pytest.mark.parametrize(
    ("what", "name", "expected"), BOUNDARY_ROWS, ids=[row[0] for row in BOUNDARY_ROWS]
)
def test_a_boundary_is_named_for_a_derived_root(what, name, expected):
    assert _boundary_lines(name) == expected, what


def test_a_boundary_outside_the_converted_packages_is_not_checked():
    assert _boundary_lines("Aggregate: Chapter", package=None) == [], "an annotation elsewhere"
    assert _boundary_lines("Aggregate: Chapter", package=99) == [], (
        "a package that is not converted"
    )


# --- PD-2: composition-named, through a conversion ------------------------------------------------------


@pytest.mark.parametrize(
    ("note", "named"), [("On the wrong connector.", True), (None, False)], ids=["noted", "plain"]
)
def test_a_note_on_a_composition_fails_the_check_in_a_conversion(note, named):
    drawn = composition(1, BOOK, CHAPTER)
    drawn.note = note
    out = run(
        model(
            klass(BOOK, "lib:Book"),
            klass(CHAPTER, "lib:Chapter"),
            links=(link(2, BOOK, CHAPTER, target_role="lib:hasChapter", target_card="0..*"),),
            compositions=(drawn,),
        )
    )
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("composition_named") == (
        ["Book -> Chapter: the association carries the note"] if named else []
    ), "the note belongs on the association"


# --- A-14: the reference collection pattern passes the check --------------------------------------------

COLLECTION, RESOURCE = 20, 21


def _reference_collection():
    """The conventions page's abstract collection whose ``dct:hasPart`` role stays the toolkit's."""
    return model(
        klass(COLLECTION, "lib:Collection", abstract=True),
        klass(RESOURCE, "lib:Resource", abstract=True),
        klass(SHELF, "lib:Shelf"),
        klass(BOOK, "lib:Book"),
        links=(
            link(1, COLLECTION, RESOURCE, target_role="dct:hasPart", target_card="0..*"),
            generalisation(2, SHELF, COLLECTION),
            generalisation(3, BOOK, RESOURCE),
            link(4, SHELF, BOOK, target_role="dct:hasPart", target_card="0..*"),
        ),
        tags=(tag(COLLECTION, "rp_mixins", "ReferenceCollection"),),
    )


def test_the_reference_collection_pattern_passes_the_check():
    out = run(_reference_collection())
    assert out.problems == [], out.problem_texts()
    assert any(line.report_kind == ReportKind.TOOLKIT_SLOT_KEPT for line in out.report), (
        "the abstract role stays the toolkit's has_part, reported toolkit-slot-kept"
    )
    failing = [line for line in out.report if ReportKind(line.report_kind) in CONVENTION_KINDS]
    assert failing == [], f"the page's own pattern gives no convention line: {failing}"
