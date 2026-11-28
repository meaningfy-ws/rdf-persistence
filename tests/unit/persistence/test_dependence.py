"""The pure fragments of dependence (dependent-aggregates PD-3, PD-6, PD-7): the pointer of a part,
the whole guard, the discovery query and the no-late-part guard, each run on a small dataset."""

import pytest
from rdflib import RDF, Dataset, Literal, URIRef

from rdf_persistence.core.domain.exceptions import InvalidBody, SparqlError
from rdf_persistence.core.domain.generated.rp_core import DependenceLink, RegistryKind
from rdf_persistence.persistence.services.dependence import (
    discovered,
    discovery_query,
    no_late_part_guard,
    pointer_of,
    whole_guard,
)
from rdf_persistence.schema.services import vocabulary as v

EX = "https://example.org/"
REGISTRY = URIRef(f"{EX}registry")
AUDIT, SPECIAL_AUDIT, OTHER = (URIRef(f"{EX}{n}") for n in ("Audit", "SpecialAudit", "Other"))
RESULT, FINDING = URIRef(f"{EX}Result"), URIRef(f"{EX}Finding")
OF_AUDIT, OF_RESULT = URIRef(f"{EX}of_audit"), URIRef(f"{EX}of_result")
A1, A2, R1, R2, F1 = (URIRef(f"{EX}{n}") for n in ("A1", "A2", "R1", "R2", "F1"))
LINKS = [
    DependenceLink(
        part_classes=[str(RESULT)],
        pointer=str(OF_AUDIT),
        whole_classes=[str(AUDIT), str(SPECIAL_AUDIT)],
    ),
    DependenceLink(
        part_classes=[str(FINDING)], pointer=str(OF_RESULT), whole_classes=[str(RESULT)]
    ),
]


def graph_of(iri: URIRef) -> URIRef:
    return URIRef(f"{iri}/graph")


def store(*aggregates: tuple[URIRef, URIRef, int, URIRef | None]) -> Dataset:
    """A dataset with one registered graph per ``(root, class, version, pointer target)``."""
    data = Dataset()
    kind = v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]
    for root, cls, version, whole in aggregates:
        graph = data.graph(graph_of(root))
        graph.add((graph_of(root), v.VERSION, Literal(version)))
        graph.add((root, RDF.type, cls))
        if whole is not None:
            pointer = OF_AUDIT if cls == RESULT else OF_RESULT
            graph.add((root, pointer, whole))
        registry = data.graph(REGISTRY)
        registry.add((graph_of(root), v.REGISTRY_KIND, kind))
        registry.add((graph_of(root), v.REGISTRY_OWNED_BY, root))
    return data


def holds(data: Dataset, guard: str) -> bool:
    """Whether the guard lets the request through: the guards are the WHERE of the start."""
    return bool(data.query(f"ASK {{ {guard} }}").askAnswer)


@pytest.mark.parametrize(
    ("triples", "expected"),
    [
        ([(R1, OF_AUDIT, A1)], A1),
        ([(R1, OF_AUDIT, A1), (R1, RDF.type, RESULT), (R2, OF_AUDIT, A2)], A1),
        ([], InvalidBody),
        ([(R1, OF_AUDIT, A1), (R1, OF_AUDIT, A2)], InvalidBody),
        ([(R1, OF_AUDIT, R1)], InvalidBody),
        ([(R1, OF_AUDIT, Literal("A1"))], InvalidBody),
        ([(R2, OF_AUDIT, A1)], InvalidBody),
    ],
    ids=["one", "other-subjects-ignored", "none", "two", "itself", "literal", "foreign-subject"],
)
def test_pointer_of(triples, expected) -> None:
    if isinstance(expected, URIRef):
        assert pointer_of(str(R1), triples, LINKS[0]) == expected, (
            "the single IRI value is the whole"
        )
    else:
        with pytest.raises(expected):
            pointer_of(str(R1), triples, LINKS[0])


@pytest.mark.parametrize(
    ("aggregates", "allowed"),
    [
        ([(A1, AUDIT, 1, None)], True),
        ([(A1, SPECIAL_AUDIT, 2, None)], True),
        ([], False),
        ([(A1, OTHER, 1, None)], False),
        ([(A2, AUDIT, 1, None)], False),
    ],
    ids=["whole", "subclass", "absent", "other-class", "other-whole"],
)
def test_whole_guard(aggregates, allowed) -> None:
    guard = whole_guard(graph_of(A1), A1, LINKS[0], 0)
    assert holds(store(*aggregates), guard) is allowed, (
        "the guard holds when the whole is a whole class"
    )


def test_whole_guards_carry_their_index() -> None:
    first, second = (whole_guard(graph_of(A1), A1, LINKS[0], n) for n in (0, 3))
    assert "?wv0" in first, "the first guard names its variables with 0"
    assert "?wv3" in second, "the later guard names its variables with 3"
    assert "?wv0" not in second, "the later guard shares none with the first"
    both = f"{first} {second}"
    assert holds(store((A1, AUDIT, 1, None)), both) is True, (
        "two guards in one request do not clash"
    )


def test_discovery_query_rows() -> None:
    data = store(
        (A1, AUDIT, 1, None),
        (R1, RESULT, 4, A1),
        (R2, RESULT, 5, A1),
        (F1, FINDING, 7, R1),
        (A2, AUDIT, 1, None),
    )
    query = discovery_query([A1, R1], LINKS, REGISTRY, 10)
    rows = sorted(discovered(r) for r in data.query(query))
    assert rows == [
        (str(A1), str(R1), str(RESULT), "4"),
        (str(A1), str(R2), str(RESULT), "5"),
        (str(R1), str(F1), str(FINDING), "7"),
    ], "each row is whole, part, type and version, of the given wholes only"


def test_discovery_query_limit_is_max_plus_one() -> None:
    data = store((A1, AUDIT, 1, None), (R1, RESULT, 1, A1), (R2, RESULT, 1, A1))
    rows = list(data.query(discovery_query([A1], LINKS, REGISTRY, 1)))
    assert len(rows) == 2, "one row more than the limit, so the caller sees it passed"


def test_discovery_query_is_filled_with_terms() -> None:
    hostile = URIRef(EX + "x> } DROP ALL #")
    with pytest.raises(SparqlError):
        discovery_query([hostile], LINKS, REGISTRY, 3)
    with pytest.raises(SparqlError):
        discovery_query([A1], LINKS, REGISTRY, -2)


@pytest.mark.parametrize(
    ("aggregates", "removed", "allowed"),
    [
        ([(A1, AUDIT, 1, None)], [A1], True),
        ([(A1, AUDIT, 1, None), (R1, RESULT, 1, A1)], [A1, R1], True),
        ([(A1, AUDIT, 1, None), (R1, RESULT, 1, A1)], [A1], False),
        ([(A1, AUDIT, 1, None), (R1, RESULT, 1, A2)], [A1], True),
        ([(A1, AUDIT, 1, None), (R1, RESULT, 1, A1), (F1, FINDING, 1, R1)], [A1, R1], False),
    ],
    ids=["no-part", "part-removed-too", "late-part", "part-of-another", "late-grandpart"],
)
def test_no_late_part_guard(aggregates, removed, allowed) -> None:
    graphs = [graph_of(r) for r in removed]
    guards = " ".join(
        no_late_part_guard(root, graphs, LINKS, REGISTRY, n) for n, root in enumerate(removed)
    )
    assert holds(store(*aggregates), guards) is allowed, (
        "the delete passes only without a late part"
    )


def test_no_late_part_guards_carry_their_index() -> None:
    first, second = (no_late_part_guard(A1, [graph_of(A1)], LINKS, REGISTRY, n) for n in (0, 2))
    assert "?lg0" in first, "the first guard names its variables with 0"
    assert "?lg2" in second, "the later guard names its variables with 2"
    assert "?lg0" not in second, "the later guard shares no variable with the first"
