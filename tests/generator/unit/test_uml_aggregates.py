"""Task 1.5: the composition tree and the derived roots, a pure pass (PD-2, PD-4..PD-6a, PD-8, D-6).

``derive_aggregates`` and ``package_kinds`` are called with hand-built records and no ``Context``.
A row succeeds when the returned ``UmlAggregates`` holds the roots, the tree, the reach and the owned
ends of its drawing and no problem; it fails (the run would stop) when a problem names the rule and
the classes the design's error matrix gives. The library domain is ``lib:`` throughout.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from linkml_runtime.linkml_model import SlotDefinition

from rdf_persistence.core.domain.generated.rp_core import ModuleKind, RpAnnotation
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    LeftOutReason,
    ReportKind,
    UmlAggregates,
    UmlClass,
    UmlComposition,
    UmlElement,
    UmlLink,
    UmlLinkKind,
    UmlName,
    UmlPackage,
    UmlRule,
    UmlTaggedValue,
)
from rdf_persistence_generation.uml.aggregates import (
    check_pointers,
    derive_aggregates,
    package_kinds,
)
from rdf_persistence_generation.uml.slots import OWNED, Usage, shape_of

DIRECTED = "Source -> Destination"
BIDIRECTIONAL = "Bi-Directional"
OWN_GRAPH = "own graph"
DOMAIN_PACKAGE, ACCESS_PACKAGE, TECHNICAL_PACKAGE = 1, 2, 3
KINDS = {DOMAIN_PACKAGE: "domain", ACCESS_PACKAGE: "access", TECHNICAL_PACKAGE: "technical"}
PACKAGE_PATHS = {
    DOMAIN_PACKAGE: ["library"],
    ACCESS_PACKAGE: ["people"],
    TECHNICAL_PACKAGE: ["tech"],
}


@dataclass
class Drawing:
    """A drawn model as the records the pass takes, built one class and one connector at a time."""

    elements: list[UmlElement] = field(default_factory=list)
    compositions: list[UmlComposition] = field(default_factory=list)
    links: list[UmlLink] = field(default_factory=list)
    parents: dict[int, str] = field(default_factory=dict)
    left_out: dict[int, LeftOutReason] = field(default_factory=dict)
    toolkit: dict[int, str] = field(default_factory=dict)
    ids: dict[str, int] = field(default_factory=dict)
    slots: dict[int, str] = field(default_factory=dict)
    usages: list[Usage] = field(default_factory=list)
    toolkit_usages: list[Usage] = field(default_factory=list)

    def _id(self, label: str) -> int:
        return self.ids.setdefault(label, len(self.ids) + 100)

    def cls(
        self,
        label: str,
        *,
        abstract: bool = False,
        tenant: bool = False,
        root: bool = False,
        enum: bool = False,
        package: int = DOMAIN_PACKAGE,
    ) -> int:
        object_id = self._id(label)
        uml = UmlClass(
            object_id=object_id, name=f"lib:{label}", object_type="Class", package_id=package
        )
        self.elements.append(
            UmlElement(
                uml_class=uml,
                resolved_name=UmlName(name=label),
                label=label,
                module_path=PACKAGE_PATHS[package],
                is_enum=enum,
                is_drawn_root=root,
                is_abstract=abstract,
                is_tenant_root=tenant,
            )
        )
        return object_id

    def gone(self, label: str, why: LeftOutReason = LeftOutReason.NOT_GENERATED) -> int:
        """A class that is not an element: not generated, outside or excluded."""
        self.left_out[self._id(label)] = why
        return self.ids[label]

    def drawn_toolkit(self, label: str) -> int:
        object_id = self.gone(label)
        self.toolkit[object_id] = label
        return object_id

    def part(self, whole: str, part: str, role: str | None = None, *, own: bool = False) -> None:
        self.compositions.append(
            UmlComposition(
                composition_id=500 + len(self.compositions),
                whole_id=self._id(whole),
                part_id=self._id(part),
                own_graph=own,
                uml_stereotype=OWN_GRAPH if own else None,
                role=role,
            )
        )

    def stereotyped(self, whole: str, part: str, stereotype: str) -> None:
        self.part(whole, part)
        self.compositions[-1].uml_stereotype = stereotype

    def assoc(self, holder: str, other: str, role: str, *, both: bool = False) -> None:
        """An association whose end at ``holder`` gives the slot ``role`` over ``other``."""
        link_id = 900 + len(self.links)
        self.slots[link_id] = f"{holder}.{role}"
        drawn_back = dict(
            source_id=self._id(other),
            target_id=self._id(holder),
            source_role=role,
            direction=BIDIRECTIONAL,
        )
        drawn_forward = dict(
            source_id=self._id(holder),
            target_id=self._id(other),
            target_role=role,
            direction=DIRECTED,
        )
        self.links.append(
            UmlLink(
                connector_id=link_id,
                link_kind=UmlLinkKind.ASSOCIATION,
                **(drawn_back if both else drawn_forward),
            )
        )

    def isa(self, child: str, parent: str) -> None:
        self.parents[self._id(child)] = parent

    def derive(self) -> UmlAggregates:
        return derive_aggregates(
            self.elements,
            self.compositions,
            self.links,
            self.parents,
            KINDS,
            self.left_out,
            self.toolkit,
            {object_id: label for label, object_id in self.ids.items()},
        )

    def point(
        self,
        holder: str,
        role: str,
        target: str,
        *,
        owned: bool = False,
        iri: str | None = None,
        toolkit: bool = False,
    ) -> None:
        """A slot ``role`` on ``holder`` over ``target``, as the usage the slot pass would give it."""
        element = next(each for each in self.elements if each.label == holder)
        written = UmlName(name=role, iri=iri or f"http://example.org/lib#{role}")
        limits = SlotDefinition(name=role)
        shape = shape_of(role, (target, None), limits, marked=(OWNED,) if owned else ())
        usage = Usage(element, (SlotDefinition(name=role), written), (1, 0, role), shape)
        (self.toolkit_usages if toolkit else self.usages).append(usage)

    def pointers(self) -> list[str]:
        """The problems of ``check_pointers`` over the usages drawn, as the text a row compares."""
        found = check_pointers(self.usages, self.toolkit_usages, self.derive(), self.elements)
        return [_text(each) for each in found]

    def label(self, object_id: int) -> str:
        return next(label for label, each in self.ids.items() if each == object_id)


def _text(problem: CheckProblem) -> str:
    return f"[{problem.rule}] {problem.element}: {problem.message}"


def roots(drawing: Drawing, found: UmlAggregates) -> set[str]:
    return {drawing.label(each) for each in found.root_ids or []}


def tree(drawing: Drawing, found: UmlAggregates) -> set[tuple[str, str]]:
    return {
        (drawing.label(row.part_id), drawing.label(row.whole_id)) for row in found.part_of or []
    }


def reach(drawing: Drawing, found: UmlAggregates) -> dict[str, set[str]]:
    return {
        drawing.label(row.part_id): {drawing.label(top) for top in row.top_ids or []}
        for row in found.reached_from or []
    }


def owned(drawing: Drawing, found: UmlAggregates) -> set[str]:
    return {drawing.slots[row.link_id] for row in found.owned_ends or []}


def problems(found: UmlAggregates) -> list[str]:
    return [f"[{each.rule}] {each.element}: {each.message}" for each in found.problems or []]


def report(found: UmlAggregates, kind: ReportKind) -> set[str]:
    return {
        f"{each.element} {each.message}"
        for each in found.report_lines or []
        if each.report_kind == kind
    }


def shelf_and_books() -> Drawing:
    """Worked example 1: a shelf and its books, depth 3, a reader pointing at a book."""
    drawing = Drawing()
    for label in ("Shelf", "Book", "Chapter", "Page", "Reader"):
        drawing.cls(label)
    for whole, part, role in (
        ("Shelf", "Book", "holds"),
        ("Book", "Chapter", "hasChapter"),
        ("Chapter", "Page", "hasPage"),
    ):
        drawing.part(whole, part)
        drawing.assoc(whole, part, role)
    drawing.assoc("Reader", "Book", "borrows")
    return drawing


def sections() -> Drawing:
    """Worked example 3: recursive sections, a part class under two tops, a pointer into a part."""
    drawing = Drawing()
    for label in ("Book", "Journal", "Section", "Reader"):
        drawing.cls(label)
    for whole, part, role in (
        ("Book", "Section", "hasSection"),
        ("Journal", "Section", "hasSection"),
        ("Section", "Section", "hasSubsection"),
    ):
        drawing.part(whole, part)
        drawing.assoc(whole, part, role)
    drawing.assoc("Reader", "Section", "cites")
    return drawing


def test_a_tree_of_depth_three_gives_one_root_and_its_parts_in_order() -> None:
    drawing = shelf_and_books()
    found = drawing.derive()
    assert problems(found) == [], "a plain tree is accepted"
    assert roots(drawing, found) == {"Shelf", "Reader"}, "Book, Chapter and Page are parts"
    assert tree(drawing, found) == {("Book", "Shelf"), ("Chapter", "Book"), ("Page", "Chapter")}
    assert reach(drawing, found) == {"Book": {"Shelf"}, "Chapter": {"Shelf"}, "Page": {"Shelf"}}
    assert owned(drawing, found) == {"Shelf.holds", "Book.hasChapter", "Chapter.hasPage"}
    assert report(found, ReportKind.ROOT) == {
        "Shelf parts Book, Chapter, Page",
        "Reader no parts",
    }, "parts in tree order, depth first"
    assert [each.element for each in found.report_lines or []] == sorted(
        each.element for each in found.report_lines or []
    ), "the lines come in a stable order"


def test_the_result_does_not_depend_on_the_order_of_the_records() -> None:
    forward = shelf_and_books()
    backward = shelf_and_books()
    backward.elements.reverse()
    backward.compositions.reverse()
    backward.links.reverse()
    assert forward.derive() == backward.derive(), "a second run is byte-identical"


def test_recursive_sections_under_two_tops_are_one_aggregate_each() -> None:
    drawing = sections()
    found = drawing.derive()
    assert problems(found) == [], "a recursion a top enters, and a part class under two tops"
    assert roots(drawing, found) == {"Book", "Journal", "Reader"}, "worked example 3"
    assert tree(drawing, found) == {
        ("Section", "Book"),
        ("Section", "Journal"),
        ("Section", "Section"),
    }
    assert reach(drawing, found) == {"Section": {"Book", "Journal"}}
    assert owned(drawing, found) == {
        "Book.hasSection",
        "Journal.hasSection",
        "Section.hasSubsection",
    }
    assert report(found, ReportKind.ROOT) == {
        "Book parts Section",
        "Journal parts Section",
        "Reader no parts",
    }, "a recursion is shown once"


def test_one_part_class_under_two_wholes_of_one_top_is_accepted() -> None:
    drawing = Drawing()
    for label in ("Book", "Chapter", "Note"):
        drawing.cls(label)
    for whole, part, role in (("Book", "Chapter", "hasChapter"), ("Book", "Note", "hasNote")):
        drawing.part(whole, part)
        drawing.assoc(whole, part, role)
    drawing.part("Chapter", "Note")
    drawing.assoc("Chapter", "Note", "hasMargin")
    found = drawing.derive()
    assert problems(found) == [], "A-2: two wholes, one top"
    assert reach(drawing, found)["Note"] == {"Book"}, "the one top"
    assert len([row for row in found.part_of or [] if drawing.label(row.part_id) == "Note"]) == 2


def test_a_cycle_no_top_enters_is_refused_naming_its_classes() -> None:
    drawing = Drawing()
    for label in ("Alpha", "Beta"):
        drawing.cls(label)
    for whole, part, role in (("Alpha", "Beta", "hasBeta"), ("Beta", "Alpha", "hasAlpha")):
        drawing.part(whole, part)
        drawing.assoc(whole, part, role)
    found = drawing.derive()
    assert roots(drawing, found) == set(), "both are parts"
    assert any(
        f"[{UmlRule.BOUNDARY_OWNED.value}]" in each
        and "Alpha" in each
        and "Beta" in each
        and "no root reaches" in each
        for each in problems(found)
    ), f"the cycle is named: {problems(found)}"


def test_the_recursion_alone_is_a_cycle_no_root_reaches() -> None:
    drawing = Drawing()
    drawing.cls("Section")
    drawing.part("Section", "Section")
    drawing.assoc("Section", "Section", "hasSubsection")
    assert problems(drawing.derive()) == [
        "[boundary_owned] Section: compositions form a cycle Section → Section that no root reaches"
    ]


def test_a_part_class_no_top_reaches_is_refused_naming_it_and_its_wholes() -> None:
    drawing = Drawing()
    drawing.cls("Container", abstract=True)
    drawing.cls("Leaf")
    drawing.part("Container", "Leaf")
    drawing.assoc("Container", "Leaf", "hasLeaf")
    assert problems(drawing.derive()) == [
        "[boundary_owned] Leaf: no root reaches it (wholes Container)"
    ], "an abstract whole with no concrete class below it is no top"


def test_what_is_not_a_root() -> None:
    drawing = shelf_and_books()
    drawing.cls("Work", abstract=True)
    drawing.cls("Genre", enum=True)
    drawing.cls("Tenant", tenant=True, package=ACCESS_PACKAGE)
    drawing.cls("Grant", package=ACCESS_PACKAGE)
    drawing.cls("Log", package=TECHNICAL_PACKAGE)
    drawing.gone("Stamp")
    drawing.drawn_toolkit("Activity")
    found = drawing.derive()
    assert roots(drawing, found) == {"Shelf", "Reader"}, (
        "not a part, concrete, domain module, not an enumeration, not the tenant root, "
        "and a generated class"
    )
    assert drawing.label(found.tenant_root_id or 0) == "Tenant", "the tenant root is named apart"
    assert problems(found) == [], "none of these is a problem"


def test_the_tenant_root_with_parts_gets_a_root_line() -> None:
    drawing = Drawing()
    drawing.cls("Tenant", tenant=True, package=ACCESS_PACKAGE)
    drawing.cls("Member", package=ACCESS_PACKAGE)
    drawing.part("Tenant", "Member")
    drawing.assoc("Tenant", "Member", "hasMember")
    found = drawing.derive()
    assert problems(found) == [], "an access part under the tenant root"
    assert report(found, ReportKind.ROOT) == {"Tenant parts Member"}
    assert reach(drawing, found) == {"Member": {"Tenant"}}


def test_part_ness_is_inherited_from_a_concrete_part_and_from_an_abstract_one() -> None:
    drawing = Drawing()
    for label in ("Book", "Chapter", "Appendix", "Item", "Note"):
        drawing.cls(label, abstract=label == "Item")
    drawing.part("Book", "Chapter")
    drawing.assoc("Book", "Chapter", "hasChapter")
    drawing.part("Book", "Item")
    drawing.assoc("Book", "Item", "hasItem")
    drawing.isa("Appendix", "Chapter")
    drawing.isa("Note", "Item")
    found = drawing.derive()
    assert problems(found) == [], "A-16"
    assert roots(drawing, found) == {"Book"}, "Appendix and Note are parts by inheritance"
    assert reach(drawing, found)["Appendix"] == {"Book"}, "reached through its concrete parent"
    assert reach(drawing, found)["Note"] == {"Book"}, "reached through its abstract parent"
    assert report(found, ReportKind.ROOT) == {"Book parts Chapter, Appendix, Item, Note"}, (
        "inherited parts are listed, each once, depth first"
    )


def test_an_abstract_whole_with_two_concrete_roots_reaches_its_part_from_both() -> None:
    drawing = Drawing()
    for label in ("Work", "Book", "Periodical", "Chapter"):
        drawing.cls(label, abstract=label == "Work")
    drawing.part("Work", "Chapter")
    drawing.assoc("Work", "Chapter", "hasChapter")
    drawing.isa("Book", "Work")
    drawing.isa("Periodical", "Work")
    found = drawing.derive()
    assert problems(found) == [], "A-4"
    assert roots(drawing, found) == {"Book", "Periodical"}, "the abstract class is no root"
    assert {"Book", "Periodical"} <= reach(drawing, found)["Chapter"], "from both concrete roots"
    assert report(found, ReportKind.ROOT) == {
        "Book parts Chapter",
        "Periodical parts Chapter",
    }, "the part the root inherits from the abstract whole"


def _packages_and_tags(
    tag: str, value: str, owner: int
) -> tuple[list[UmlPackage], list[UmlTaggedValue]]:
    packages = [
        UmlPackage(package_id=pid, name=f"p{pid}", object_id=pid + 1000) for pid in (1, 2, 3)
    ]
    return packages, [UmlTaggedValue(owner_id=owner, name=tag, tag_value=value)]


@pytest.mark.parametrize(
    ("tag", "value", "owner", "expected"),
    [
        ("module_kind", "access", 1002, {1: "domain", 2: "access", 3: "domain"}),
        ("module_kind", "Technical", 1003, {1: "domain", 2: "domain", 3: "technical"}),
        ("module_kind", "access", 2, {1: "domain", 2: "domain", 3: "domain"}),
        ("rp_path", "access", 1002, {1: "domain", 2: "domain", 3: "domain"}),
    ],
    ids=["tagged", "case-blind", "a class owner is no package", "another tag"],
)
def test_package_kinds_read_the_tagged_value_and_default_to_domain(
    tag: str, value: str, owner: int, expected: dict[int, str]
) -> None:
    packages, tags = _packages_and_tags(tag, value, owner)
    assert package_kinds(packages, tags) == expected, "A-5: from tags, nothing reported"


def _agreeing() -> Drawing:
    drawing = shelf_and_books()
    drawing.elements[0].is_drawn_root = True  # Shelf
    drawing.elements[4].is_drawn_root = True  # Reader
    return drawing


def _drawn_on_a_part() -> Drawing:
    drawing = _agreeing()
    drawing.elements[1].is_drawn_root = True  # Book
    return drawing


def _derived_not_drawn() -> Drawing:
    drawing = _agreeing()
    drawing.elements[4].is_drawn_root = False  # Reader
    return drawing


def _abstract_root() -> Drawing:
    drawing = _agreeing()
    drawing.cls("Work", abstract=True, root=True)
    return drawing


def _access_root() -> Drawing:
    drawing = _agreeing()
    drawing.cls("Grant", root=True, package=ACCESS_PACKAGE)
    return drawing


AGREE = {"model 2 «root» stereotypes agree with the derived roots; drop them"}


@pytest.mark.parametrize(
    ("build", "expected_problems", "expected_lines"),
    [
        (_agreeing, [], AGREE),
        (_drawn_on_a_part, ["[root_class] Book: drawn «root» but a part of Shelf"], set()),
        (
            _derived_not_drawn,
            ["[root_class] Reader: a root (no composition's part) but not drawn «root»"],
            set(),
        ),
        (
            _abstract_root,
            ["[root_class] Work: abstract «root»: drop it, the abstract-root rule derives it"],
            set(),
        ),
        (_access_root, [], AGREE),
        (shelf_and_books, [], set()),
    ],
    ids=[
        "agreeing: deprecated-root",
        "drawn on a part",
        "derived and not drawn",
        "abstract root (A-12)",
        "access root kept (A-12)",
        "no root drawn at all",
    ],
)
def test_dec_6_compares_the_drawn_roots_with_the_derived_ones(
    build: Callable[[], Drawing], expected_problems: list[str], expected_lines: set[str]
) -> None:
    found = build().derive()
    assert problems(found) == expected_problems, "DEC-6 problems"
    assert report(found, ReportKind.DEPRECATED_ROOT) == expected_lines, "the agreeing line"


def _counting(part_is_generated: bool = False, own: bool = True) -> Drawing:
    drawing = Drawing()
    drawing.cls("ShelfCount")
    if part_is_generated:
        drawing.cls("CountReport")
    else:
        drawing.gone("CountReport")
    drawing.part("ShelfCount", "CountReport", own=own)
    drawing.assoc("ShelfCount", "CountReport", "countReport")
    return drawing


def _own_graph_in_own_graph() -> Drawing:
    drawing = _counting()
    drawing.gone("ShapeReport")
    drawing.part("CountReport", "ShapeReport", own=True)
    drawing.cls("ShapeResult")
    drawing.part("ShapeReport", "ShapeResult")
    drawing.assoc("ShapeReport", "ShapeResult", "result")
    return drawing


def _not_generated_under_not_generated() -> Drawing:
    drawing = Drawing()
    drawing.cls("Shelf")
    drawing.gone("CountReport")
    drawing.gone("ShapeReport")
    drawing.part("CountReport", "ShapeReport")
    drawing.part("Shelf", "CountReport", own=True)
    drawing.assoc("Shelf", "CountReport", "countReport")
    return drawing


@pytest.mark.parametrize(
    ("build", "expected_problems", "left_inside"),
    [
        (_counting, [], []),
        (
            lambda: _counting(part_is_generated=True),
            [],
            [],
        ),
        (
            lambda: _counting(own=False),
            [
                "[boundary_owned] ShelfCount -> CountReport: a not-generated part is stored "
                "apart: use «own graph»"
            ],
            [],
        ),
        (_own_graph_in_own_graph, [], ["ShapeResult"]),
        (_not_generated_under_not_generated, [], []),
    ],
    ids=[
        "own graph to a not-generated part",
        "own graph to a generated part, a dependent root (PD-13)",
        "plain composition to a not-generated part",
        "own graph nested, a plain part inside (A-8)",
        "not-generated part under a not-generated whole (A-8)",
    ],
)
def test_own_graph_compositions(
    build: Callable[[], Drawing], expected_problems: list[str], left_inside: list[str]
) -> None:
    drawing = build()
    found = drawing.derive()
    assert problems(found) == expected_problems, "DEC-7 and A-8"
    assert sorted(drawing.label(each) for each in found.left_inside_ids or []) == left_inside


def test_an_own_graph_part_gives_a_tree_row_but_no_owned_slot_and_no_part_in_the_line() -> None:
    drawing = _counting()
    found = drawing.derive()
    assert [(row.own_graph) for row in found.part_of or []] == [True], "the row says own graph"
    assert owned(drawing, found) == set(), "the slot ranges over uri, it is not owned"
    assert report(found, ReportKind.ROOT) == {"ShelfCount no parts"}, "example 2"


@pytest.mark.parametrize(
    ("own", "expected"),
    [(True, {"ShelfCount.countReport"}), (False, set())],
    ids=["own graph", "plain composition"],
)
def test_loaded_graph_ends_hold_the_slot_of_an_own_graph_composition_to_a_not_generated_part(
    own: bool, expected: set[str]
) -> None:
    drawing = _counting(own=own)
    found = drawing.derive()
    ends = {drawing.slots[row.link_id] for row in found.loaded_graph_ends or []}
    assert ends == expected, "D-9: only an own-graph end to a not-generated part is marked"
    assert owned(drawing, found) == set(), "a loaded-graph end is never owned"


def test_a_class_inside_an_own_graph_is_in_no_aggregate_and_no_root() -> None:
    drawing = _own_graph_in_own_graph()
    found = drawing.derive()
    assert roots(drawing, found) == {"ShelfCount"}, "ShapeResult is left inside, not a root"
    assert tree(drawing, found) >= {("CountReport", "ShelfCount")}, "the own-graph row is kept"
    assert "ShapeResult" not in {part for part, _ in tree(drawing, found)}, "exempt composition"


@pytest.mark.parametrize("inside_is_child", [True, False], ids=["child", "parent"])
def test_a_generalisation_to_or_from_a_class_inside_an_own_graph_is_refused(
    inside_is_child: bool,
) -> None:
    drawing = _own_graph_in_own_graph()
    drawing.cls("Other")
    if inside_is_child:
        drawing.isa("ShapeResult", "Other")
    else:
        drawing.isa("Other", "ShapeResult")
    found = drawing.derive()
    assert any(
        "inside the own graph of ShapeReport; it cannot take part in a generalisation" in each
        for each in problems(found)
    ), f"A-7: {problems(found)}"


def test_a_generalisation_between_two_classes_inside_an_own_graph_is_refused_once() -> None:
    """D-13 W1: one generalisation, one problem, though both its ends are inside."""
    drawing = _own_graph_in_own_graph()
    drawing.cls("ShapeDetail")
    drawing.part("ShapeReport", "ShapeDetail")
    drawing.assoc("ShapeReport", "ShapeDetail", "detail")
    drawing.isa("ShapeDetail", "ShapeResult")
    refused = [each for each in problems(drawing.derive()) if "generalisation" in each]
    assert refused == [
        "[boundary_owned] ShapeDetail: inside the own graph of ShapeReport; "
        "it cannot take part in a generalisation"
    ], "the child end names the generalisation once"


def test_the_module_kind_the_pass_reads_is_the_generated_enum_value() -> None:
    """D-13 W4: the tag name and the default kind are the metamodel's, not a second copy."""
    packages = [
        UmlPackage(package_id=1, name="a", object_id=11),
        UmlPackage(package_id=2, name="b"),
    ]
    tags = [
        UmlTaggedValue(owner_id=11, name=RpAnnotation.MODULE_KIND.value, tag_value=" Technical ")
    ]
    assert package_kinds(packages, tags) == {1: "technical", 2: ModuleKind.DOMAIN.value}, (
        "read case-blind from the generated tag name; the default is the generated DOMAIN"
    )


def _other_stereotype() -> Drawing:
    drawing = shelf_and_books()
    drawing.compositions[0].uml_stereotype = "loaded"
    return drawing


def _outside_part() -> Drawing:
    drawing = Drawing()
    drawing.cls("Shelf")
    drawing.gone("Stranger", LeftOutReason.OUTSIDE)
    drawing.part("Shelf", "Stranger")
    drawing.assoc("Shelf", "Stranger", "holds")
    return drawing


def _excluded_whole() -> Drawing:
    drawing = Drawing()
    drawing.gone("Stranger", LeftOutReason.EXCLUDED)
    drawing.cls("Page")
    drawing.part("Stranger", "Page")
    drawing.assoc("Stranger", "Page", "holds")
    return drawing


def _toolkit_part() -> Drawing:
    drawing = Drawing()
    drawing.cls("Shelf")
    drawing.drawn_toolkit("Activity")
    drawing.part("Shelf", "Activity")
    drawing.assoc("Shelf", "Activity", "log")
    return drawing


def _enumeration_part() -> Drawing:
    drawing = Drawing()
    drawing.cls("Shelf")
    drawing.cls("Genre", enum=True)
    drawing.part("Shelf", "Genre")
    drawing.assoc("Shelf", "Genre", "genre")
    return drawing


def _tenant_part() -> Drawing:
    drawing = Drawing()
    drawing.cls("Tenant", tenant=True)
    drawing.cls("Shelf")
    drawing.part("Shelf", "Tenant")
    drawing.assoc("Shelf", "Tenant", "tenant")
    return drawing


def _technical_part() -> Drawing:
    drawing = Drawing()
    drawing.cls("Shelf")
    drawing.cls("Log", package=TECHNICAL_PACKAGE)
    drawing.part("Shelf", "Log")
    drawing.assoc("Shelf", "Log", "log")
    return drawing


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (
            _other_stereotype,
            ["[no_rule] Shelf -> Book: connector stereotype loaded: no rule converts it"],
        ),
        (
            _outside_part,
            ["[boundary_owned] Shelf -> Stranger: the composition crosses the converted subtree"],
        ),
        (
            _excluded_whole,
            ["[boundary_owned] Stranger -> Page: the composition crosses the converted subtree"],
        ),
        (
            _toolkit_part,
            [
                "[boundary_owned] Shelf -> Activity: toolkit classes are composed by mixins, not compositions"
            ],
        ),
        (
            _enumeration_part,
            ["[no_rule] Shelf -> Genre: composition to an enumeration: no rule converts it"],
        ),
        (_tenant_part, ["[root_class] Tenant: the tenant root cannot be a part"]),
        (
            _technical_part,
            [
                "[boundary_owned] Shelf -> Log: a domain part cannot live in module kind technical (packages library, tech)"
            ],
        ),
    ],
    ids=[
        "other stereotype",
        "part outside",
        "whole excluded",
        "toolkit part",
        "enumeration part",
        "tenant root as part",
        "domain whole, technical part (A-25)",
    ],
)
def test_ends_that_are_not_converted_classes_and_the_other_composition_refusals(
    build: Callable[[], Drawing], expected: list[str]
) -> None:
    assert problems(build().derive()) == expected, "A-9, A-25, PD-8"


def _book_and_chapter() -> Drawing:
    drawing = Drawing()
    drawing.cls("Book")
    drawing.cls("Chapter")
    return drawing


def _no_association() -> Drawing:
    drawing = _book_and_chapter()
    drawing.part("Book", "Chapter")
    return drawing


def _one_association_with_a_role_on_the_composition() -> Drawing:
    drawing = _book_and_chapter()
    drawing.part("Book", "Chapter", "hasChapter")
    drawing.assoc("Book", "Chapter", "hasChapter")
    return drawing


def _two_without_a_role() -> Drawing:
    drawing = _book_and_chapter()
    drawing.part("Book", "Chapter")
    drawing.assoc("Book", "Chapter", "hasChapter")
    drawing.assoc("Book", "Chapter", "firstChapter")
    return drawing


def _two_and_the_role_names_one() -> Drawing:
    drawing = _book_and_chapter()
    drawing.part("Book", "Chapter", "hasChapter")
    drawing.assoc("Book", "Chapter", "hasChapter")
    drawing.assoc("Book", "Chapter", "firstChapter")
    return drawing


def _role_names_no_candidate() -> Drawing:
    drawing = _book_and_chapter()
    drawing.part("Book", "Chapter", "lastChapter")
    drawing.assoc("Book", "Chapter", "hasChapter")
    return drawing


def _to_a_subclass_of_the_part() -> Drawing:
    drawing = _book_and_chapter()
    drawing.cls("Appendix")
    drawing.isa("Appendix", "Chapter")
    drawing.part("Book", "Chapter")
    drawing.assoc("Book", "Appendix", "hasAppendix")
    return drawing


def _to_a_superclass_of_the_part() -> Drawing:
    drawing = _book_and_chapter()
    drawing.cls("Appendix")
    drawing.isa("Appendix", "Chapter")
    drawing.part("Book", "Appendix")
    drawing.assoc("Book", "Chapter", "hasChapter")
    return drawing


def _book_and_chapter_one_unnamed() -> Drawing:
    drawing = _book_and_chapter()
    drawing.part("Book", "Chapter")
    drawing.assoc("Book", "Chapter", "hasChapter")
    return drawing


def _drawn_bidirectional_from_the_part() -> Drawing:
    drawing = _book_and_chapter()
    drawing.part("Book", "Chapter")
    drawing.assoc("Book", "Chapter", "hasChapter", both=True)
    return drawing


@pytest.mark.parametrize(
    ("build", "expected_problems", "expected_owned"),
    [
        (
            _no_association,
            [
                "[boundary_owned] Book -> Chapter: a composition needs an association Book -> Chapter that names the role"
            ],
            set(),
        ),
        (_one_association_with_a_role_on_the_composition, [], {"Book.hasChapter"}),
        (
            _two_without_a_role,
            [
                "[boundary_owned] Book -> Chapter: two associations (firstChapter, hasChapter) beside one composition; name one on the composition"
            ],
            set(),
        ),
        (_two_and_the_role_names_one, [], {"Book.hasChapter"}),
        (
            _role_names_no_candidate,
            [
                "[boundary_owned] Book -> Chapter: role lastChapter names no association Book -> Chapter"
            ],
            set(),
        ),
        (
            _to_a_subclass_of_the_part,
            [
                "[boundary_owned] Book -> Chapter: a composition needs an association Book -> Chapter that names the role"
            ],
            set(),
        ),
        (
            _to_a_superclass_of_the_part,
            [
                "[boundary_owned] Book -> Appendix: a composition needs an association Book -> Appendix that names the role"
            ],
            set(),
        ),
        (_drawn_bidirectional_from_the_part, [], {"Book.hasChapter"}),
    ],
    ids=[
        "none",
        "one, role on the composition",
        "two, no role",
        "two, the role names one",
        "a role naming no candidate",
        "association to the part's subclass (A-17)",
        "association to the part's superclass (A-17)",
        "bi-directional, the part-side role",
    ],
)
def test_the_association_beside_a_composition(
    build: Callable[[], Drawing], expected_problems: list[str], expected_owned: set[str]
) -> None:
    drawing = build()
    found = drawing.derive()
    assert problems(found) == expected_problems, "PD-2 and D-6"
    assert owned(drawing, found) == expected_owned, "the owned ends are the matched associations"


@pytest.mark.parametrize(
    ("build", "named"),
    [
        (_one_association_with_a_role_on_the_composition, True),
        (_two_and_the_role_names_one, False),
        (_book_and_chapter_one_unnamed, False),
    ],
    ids=["one candidate and a role", "two candidates, the role chooses", "one candidate, no role"],
)
def test_a_role_where_one_candidate_makes_it_unneeded_is_a_composition_named_line(
    build: Callable[[], Drawing], named: bool
) -> None:
    found = build().derive()
    assert report(found, ReportKind.COMPOSITION_NAMED) == (
        {"Book -> Chapter the association carries the role"} if named else set()
    ), "PD-2: a role the single candidate makes unneeded is presentation"


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("Written on the wrong connector.", {"Book -> Chapter the association carries the note"}),
        ("  ", set()),
        (None, set()),
    ],
    ids=["a note", "a blank note", "no note"],
)
def test_a_note_on_a_composition_is_a_composition_named_line(
    note: str | None, expected: set[str]
) -> None:
    drawing = _book_and_chapter_one_unnamed()
    drawing.compositions[0].note = note
    found = drawing.derive()
    assert report(found, ReportKind.COMPOSITION_NAMED) == expected, (
        "the association carries the description, not the composition"
    )


def test_two_owned_roles_to_one_part_class_beside_an_internal_reference() -> None:
    drawing = Drawing()
    for label in ("Book", "Section"):
        drawing.cls(label)
    drawing.part("Book", "Section", "frontMatter")
    drawing.part("Book", "Section", "body")
    for role in ("frontMatter", "body", "firstSection"):
        drawing.assoc("Book", "Section", role)
    found = drawing.derive()
    assert problems(found) == [], "A-3"
    assert owned(drawing, found) == {"Book.frontMatter", "Book.body"}, (
        "the reference stays a pointer"
    )


def test_a_composition_under_a_not_generated_whole_needs_no_association() -> None:
    drawing = Drawing()
    drawing.gone("Report")
    drawing.cls("Result")
    drawing.part("Report", "Result")
    assert problems(drawing.derive()) == [], "A-8: it converts to nothing, so every rule is exempt"


HAS_PART = "http://purl.org/dc/terms/hasPart"


def _library() -> Drawing:
    """Book and Journal share Section; Reader, a tenant root and every other kind of class stand apart."""
    drawing = Drawing()
    for label in ("Book", "Journal", "Section", "Reader"):
        drawing.cls(label)
    drawing.cls("Tenant", tenant=True)
    drawing.cls("Publication", abstract=True)
    drawing.cls("Mixed", abstract=True)
    drawing.cls("Staff", package=ACCESS_PACKAGE)
    drawing.cls("Currency", package=TECHNICAL_PACKAGE)
    for whole in ("Book", "Journal"):
        drawing.part(whole, "Section")
        drawing.assoc(whole, "Section", "hasSection")
        drawing.point(whole, "hasSection", "Section", owned=True)
        drawing.isa(whole, "Publication")
    drawing.isa("Section", "Mixed")
    drawing.isa("Reader", "Mixed")
    return drawing


def _pointing(target: str, holder: str = "Reader") -> Drawing:
    drawing = _library()
    drawing.point(holder, "cites", target)
    return drawing


def _owned_and_pointing(*, kept: bool = False, toolkit: bool = False) -> Drawing:
    drawing = _library()
    drawing.point("Book", "hasPart", "Section", owned=True, iri=HAS_PART, toolkit=toolkit)
    drawing.point("Reader", "hasPart", "Book", iri=HAS_PART, toolkit=toolkit)
    if kept:
        drawing.point("Reader", "hasPart", "Book", toolkit=True, iri=HAS_PART)
    return drawing


def _owned_only() -> Drawing:
    drawing = _library()
    drawing.point("Book", "hasPart", "Section", owned=True, iri=HAS_PART)
    return drawing


def _pointers_only() -> Drawing:
    drawing = _library()
    drawing.point("Reader", "hasPart", "Book", iri=HAS_PART)
    drawing.point("Staff", "hasPart", "Journal", iri=HAS_PART)
    return drawing


SECTION_REFUSED = [
    "[boundary_owned] Reader.cites: points at Section, a part of Book, Journal; "
    "point at Book or Journal"
]
ROLE_SPLIT = ["[boundary_owned] hasPart: role hasPart is owned on Book and a pointer on Reader"]


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (lambda: _pointing("Section"), SECTION_REFUSED),
        (lambda: _pointing("Section", "Staff"), [SECTION_REFUSED[0].replace("Reader", "Staff")]),
        (lambda: _pointing("Book"), []),
        (lambda: _pointing("Journal"), []),
        (lambda: _pointing("Tenant"), []),
        (lambda: _pointing("Publication"), []),
        (lambda: _pointing("Section", "Book"), []),
        (lambda: _pointing("Section", "Section"), []),
        (lambda: _pointing("Staff"), []),
        (lambda: _pointing("Currency"), []),
        (lambda: _pointing("Mixed"), []),
        (_owned_and_pointing, ROLE_SPLIT),
        (_owned_only, []),
        (_pointers_only, []),
        (lambda: _owned_and_pointing(toolkit=True), []),
        (lambda: _owned_and_pointing(kept=True), []),
    ],
    ids=[
        "into another aggregate's part, naming slot, part and roots",
        "into a part from a class of no aggregate",
        "to a root",
        "to another root",
        "to the tenant root",
        "to an abstract class whose descendants are all roots",
        "to a part of the aggregate the holder is the top of",
        "to a part from a part of the same aggregate",
        "to an access class",
        "to a technical class",
        "to an abstract class mixing a root and a part",
        "a role owned on one whole and a pointer elsewhere (C-9)",
        "a role owned and no pointer",
        "a role used as pointers only",
        "the same role kept as the toolkit's slot, owned and pointing (A-26)",
        "the role is the toolkit's besides a domain pointer (A-26)",
    ],
)
def test_pointers_target_roots_only(build: Callable[[], Drawing], expected: list[str]) -> None:
    assert build().pointers() == expected, "PD-10 and C-9: only a part of another aggregate refused"


def test_a_pointer_refused_for_its_target_is_not_refused_again_for_its_role() -> None:
    drawing = _library()
    drawing.point("Book", "cites", "Section", owned=True)
    drawing.point("Reader", "cites", "Section")
    assert len(drawing.pointers()) == 1, "one slot gives one problem, the target's (PD-10)"
