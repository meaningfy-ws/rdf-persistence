"""The SPARQL the session sends (PD-5, PD-7, PD-8), run against an in-memory rdflib dataset."""

from datetime import UTC, datetime

import pytest
from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_core import RegistryEntry, RegistryKind
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.session import (
    add_text,
    payload_triples,
    registry_triples,
    remove_text,
    replace_text,
)

EX = "http://example.org/t/"
ROOT, OTHER_ROOT = URIRef(f"{EX}books/1"), URIRef(f"{EX}books/2")
GRAPH, OTHER = URIRef(f"{ROOT}/graph"), URIRef(f"{OTHER_ROOT}/graph")
REGISTRY = URIRef(f"{EX}registry")
TITLE = URIRef("http://purl.org/dc/terms/title")
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
ME = "http://example.org/people/me"


def entry(graph: URIRef, root: URIRef) -> RegistryEntry:
    return RegistryEntry(graph=str(graph), kind=RegistryKind.AGGREGATE, owned_by=str(root))


def payload(graph: URIRef, root: URIRef, title: str, version: str) -> list:
    tracking = Tracked(created=NOW, creator=ME)
    return payload_triples(graph, version, tracking, [(root, TITLE, Literal(title))])


def seeded() -> Dataset:
    """Two committed aggregates, each with a registry entry."""
    dataset = Dataset()
    for graph, root, version in ((GRAPH, ROOT, "v1"), (OTHER, OTHER_ROOT, "w1")):
        dataset.update(
            add_text(graph, REGISTRY, payload(graph, root, "old", version), [entry(graph, root)])
        )
    return dataset


def contents(dataset: Dataset, graph: URIRef) -> Graph:
    copy = Graph()
    for triple in dataset.graph(graph):
        copy.add(triple)
    return copy


def assert_same(actual: Graph, expected: Graph, message: str) -> None:
    assert isomorphic(actual, expected), f"{message}: {graph_diff(actual, expected)}"


def test_add_writes_the_triples_and_the_registry_entry_to_their_graphs():
    dataset = seeded()
    expected = Graph()
    for triple in payload(GRAPH, ROOT, "old", "v1"):
        expected.add(triple)
    assert_same(contents(dataset, GRAPH), expected, "aggregate graph")
    registry = contents(dataset, REGISTRY)
    assert (GRAPH, v.REGISTRY_OWNED_BY, ROOT) in registry, "entry names the owner"
    assert (GRAPH, v.REGISTRY_KIND, v.REGISTRY_KIND_IRIS["aggregate"]) in registry, "entry kind"
    assert len(contents(dataset, REGISTRY)) == 6, "two entries of three statements"


@pytest.mark.parametrize(
    ("guard", "replaced"),
    [("v1", True), ("stale", False), ("w1", False)],
    ids=["match", "stale", "other-aggregates-version"],
)
def test_replace_runs_only_when_the_guard_matches(guard, replaced):
    dataset = seeded()
    before = contents(dataset, GRAPH)
    dataset.update(
        replace_text(
            GRAPH, REGISTRY, ROOT, guard, payload(GRAPH, ROOT, "new", "v2"), [entry(GRAPH, ROOT)]
        )
    )
    after = contents(dataset, GRAPH)
    if replaced:
        assert (ROOT, TITLE, Literal("new")) in after, "new triple stored"
        assert (ROOT, TITLE, Literal("old")) not in after, "old triple gone"
        assert (GRAPH, v.VERSION, Literal("v2")) in after, "new version stored"
        assert (GRAPH, v.VERSION, Literal("v1")) not in after, "old version gone"
    else:
        assert_same(after, before, "a stale guard changes nothing")


def test_replace_keeps_one_registry_entry_and_leaves_other_aggregates_alone():
    dataset = seeded()
    other_before = (contents(dataset, OTHER), contents(dataset, REGISTRY))
    dataset.update(
        replace_text(
            GRAPH, REGISTRY, ROOT, "v1", payload(GRAPH, ROOT, "new", "v2"), [entry(GRAPH, ROOT)]
        )
    )
    assert_same(contents(dataset, OTHER), other_before[0], "other aggregate")
    assert_same(contents(dataset, REGISTRY), other_before[1], "registry: replaced entry is equal")


def test_replace_of_a_graph_without_registry_entry_writes_none():
    dataset = Dataset()
    meta = URIRef(f"{EX}meta")
    dataset.update(add_text(meta, REGISTRY, payload(meta, URIRef(EX), "a", "m1"), []))
    dataset.update(
        replace_text(meta, REGISTRY, URIRef(EX), "m1", payload(meta, URIRef(EX), "b", "m2"), [])
    )
    assert len(contents(dataset, REGISTRY)) == 0, "the tenant root has no registry entry"
    assert (URIRef(EX), TITLE, Literal("b")) in contents(dataset, meta), "meta graph replaced"


@pytest.mark.parametrize(("guard", "removed"), [("v1", True), ("stale", False)])
def test_remove_deletes_graph_and_entries_only_when_the_guard_matches(guard, removed):
    dataset = seeded()
    before = contents(dataset, GRAPH)
    dataset.update(remove_text(GRAPH, REGISTRY, ROOT, guard))
    if removed:
        assert len(contents(dataset, GRAPH)) == 0, "graph emptied"
        assert (GRAPH, v.REGISTRY_OWNED_BY, ROOT) not in contents(dataset, REGISTRY), "entry gone"
        assert (OTHER, v.REGISTRY_OWNED_BY, OTHER_ROOT) in contents(dataset, REGISTRY), "other kept"
    else:
        assert_same(contents(dataset, GRAPH), before, "a stale guard changes nothing")
        assert (GRAPH, v.REGISTRY_OWNED_BY, ROOT) in contents(dataset, REGISTRY), "entry kept"


def test_remove_also_deletes_the_entries_of_loaded_graphs_owned_by_the_root():
    dataset = seeded()
    loaded = URIRef(f"{ROOT}/content/1")
    loaded_entry = RegistryEntry(
        graph=str(loaded), kind=RegistryKind.LOADED_GRAPH, owned_by=str(ROOT)
    )
    for triple in registry_triples(loaded_entry):
        dataset.graph(REGISTRY).add(triple)
    dataset.update(remove_text(GRAPH, REGISTRY, ROOT, "v1"))
    assert (loaded, v.REGISTRY_OWNED_BY, ROOT) not in contents(dataset, REGISTRY), (
        "loaded entry gone"
    )


def test_payload_of_a_first_commit_has_version_created_and_creator_only():
    triples = set(payload_triples(GRAPH, "v1", Tracked(created=NOW, creator=ME), []))
    assert {p for _, p, _ in triples} == {v.VERSION, v.CREATED, v.CREATOR}, (
        "no modified, no contributor"
    )
    assert all(s == GRAPH for s, _, _ in triples), "all about the graph IRI"


def test_payload_of_a_later_commit_adds_modified_and_every_contributor():
    tracking = Tracked(
        created=NOW,
        creator=ME,
        modified=NOW,
        contributor=["http://example.org/a", "http://example.org/b"],
    )
    triples = set(payload_triples(GRAPH, "v2", tracking, []))
    contributors = {o for _, p, o in triples if p == v.CONTRIBUTOR}
    assert contributors == {URIRef("http://example.org/a"), URIRef("http://example.org/b")}, (
        "contributors"
    )
    assert (GRAPH, v.MODIFIED, Literal(NOW)) in triples, "modified"


@pytest.mark.parametrize("predicate", sorted(v.BOOKKEEPING_PREDICATES))
def test_payload_drops_incoming_bookkeeping_about_the_graph_iri(predicate):
    forged = (GRAPH, predicate, Literal("forged"))
    triples = payload_triples(GRAPH, "v1", Tracked(created=NOW, creator=ME), [forged])
    assert forged not in triples, f"{predicate} from the caller is not stored"


def test_payload_keeps_other_statements_about_the_graph_iri():
    own = (GRAPH, TITLE, Literal("kept"))
    assert own in payload_triples(GRAPH, "v1", Tracked(created=NOW, creator=ME), [own])


def skolem_prefix(graph: URIRef) -> str:
    return f"{graph}/.well-known/genid/"


def with_blank_nodes(root: URIRef) -> list:
    """Two blank nodes: one used twice (as object and as subject), one only as an object."""
    shared, lone = BNode("shared"), BNode("lone")
    return [
        (root, TITLE, shared),
        (shared, TITLE, Literal("part")),
        (shared, TITLE, lone),
        (root, TITLE, Literal("plain")),
    ]


def test_payload_replaces_each_blank_node_by_one_skolem_iri_under_the_graph_iri():
    triples = payload_triples(GRAPH, "v1", Tracked(created=NOW, creator=ME), with_blank_nodes(ROOT))
    nodes = {n for t in triples for n in t}
    assert not any(isinstance(n, BNode) for n in nodes), "no blank node is written"
    skolems = {n for n in nodes if str(n).startswith(skolem_prefix(GRAPH))}
    assert len(skolems) == 2, "one skolem IRI per blank node, the same node mapping to the same IRI"
    assert all(isinstance(n, URIRef) for n in skolems), "skolem nodes are IRIs"
    assert len(triples) == 4 + 3, "four statements, version, created and creator"


def test_payload_gives_a_blank_node_a_fresh_skolem_on_every_write():
    first = payload_triples(GRAPH, "v1", Tracked(created=NOW, creator=ME), with_blank_nodes(ROOT))
    second = payload_triples(GRAPH, "v2", Tracked(created=NOW, creator=ME), with_blank_nodes(ROOT))
    mint = lambda ts: {n for t in ts for n in t if str(n).startswith(skolem_prefix(GRAPH))}  # noqa: E731
    assert not mint(first) & mint(second), "never reused between writes"


def test_replace_stores_blank_node_statements_once_though_the_guard_matches_many_rows():
    dataset = seeded()  # the old graph has several rows, so the template is inserted per row
    tracking = Tracked(created=NOW, creator=ME, modified=NOW)
    new = payload_triples(GRAPH, "v2", tracking, with_blank_nodes(ROOT))
    dataset.update(replace_text(GRAPH, REGISTRY, ROOT, "v1", new, [entry(GRAPH, ROOT)]))
    stored = contents(dataset, GRAPH)
    assert set(stored) == set(new), "exactly the statements written, none copied per matched row"
    assert len(stored) == len(new), "a duplicate would show as a longer graph"


def test_registry_entry_of_a_loaded_graph_is_written_replaced_and_removed_with_the_aggregate():
    loaded = [URIRef(f"{ROOT}/content/1"), URIRef(f"{ROOT}/content/2")]
    entries = [
        entry(GRAPH, ROOT),
        *(
            RegistryEntry(graph=str(g), kind=RegistryKind.LOADED_GRAPH, owned_by=str(ROOT))
            for g in loaded
        ),
    ]
    dataset = Dataset()
    dataset.update(add_text(GRAPH, REGISTRY, payload(GRAPH, ROOT, "a", "v1"), entries))
    kind = v.REGISTRY_KIND_IRIS["loaded_graph"]
    held = contents(dataset, REGISTRY)
    assert {g for g in loaded if (g, v.REGISTRY_KIND, kind) in held} == set(loaded), "written"
    dataset.update(
        replace_text(GRAPH, REGISTRY, ROOT, "v1", payload(GRAPH, ROOT, "b", "v2"), entries[:2])
    )
    held = contents(dataset, REGISTRY)
    assert (loaded[0], v.REGISTRY_KIND, kind) in held, "the kept loaded graph stays registered"
    assert (loaded[1], v.REGISTRY_KIND, kind) not in held, "the dropped one is unregistered"
    dataset.update(remove_text(GRAPH, REGISTRY, ROOT, "v2"))
    assert len(contents(dataset, REGISTRY)) == 0, "removing the aggregate removes every entry"
