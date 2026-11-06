"""The mapper between generated objects and the graph of an aggregate (PD-7, PD-7a, PD-8a, PD-10)."""

import json
from functools import cache

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import BaseModel
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.domain.iris import graph_iri, meta_graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.mapper import new_part
from rdf_persistence.services.schema_structure import is_bookkeeping, is_internal
from rdf_persistence.testkit.conformance import Conformance
from rdf_persistence.testkit.roundtrip import rdf_of
from rdf_persistence.testkit.strategies import aggregate
from tests.fixtures.library.generated.books import Book, Chapter, Genre
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.fixtures.library.generated.scans import Scan
from tests.toy import ADA, TENANT, TOY_SCHEMA, book_iri, dune, toy_mapper
from tests.toy import access as toy_access

SCHEMA = URIRef("http://schema.org/")
ROOT_CLASSES = {"Book": Book, "Scan": Scan, "Library": Library, "LibraryAccess": LibraryAccess}


def storage_of(cls: type[BaseModel], iri: str) -> URIRef:
    """The named graph that holds the root: the meta graph for the tenant root, else its own graph."""
    return meta_graph_iri(iri) if cls is Library else graph_iri(iri)


# deterministic examples, no deadline: building the strategies is slow the first time
DRAWN = settings(
    max_examples=20, deadline=None, derandomize=True, suppress_health_check=list(HealthCheck)
)


@cache
def toy() -> Conformance:
    """Opened once, not a fixture, so that Hypothesis does not print it into a failure."""
    return Conformance.of(TOY_SCHEMA)


def tracking_names(cls: type[BaseModel]) -> list[str]:
    view = toy_mapper().view
    return [s.name for s in view.class_induced_slots(cls.__name__) if is_bookkeeping(s)]


def untracked(obj: BaseModel) -> BaseModel:
    """``obj`` without the tracking slots, which the mapper does not write."""
    return obj.model_copy(update={name: None for name in tracking_names(type(obj))})


def canonical(value: object) -> object:
    """JSON of an object with every list sorted: RDF keeps no order among the values of a slot."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {k: canonical(item) for k, item in value.items()}
    if isinstance(value, list):
        return sorted(
            (canonical(item) for item in value), key=lambda i: json.dumps(i, sort_keys=True)
        )
    return value


def assert_same_graph(actual: Graph, expected: Graph) -> None:
    assert isomorphic(actual, expected), (
        f"only actual: {sorted(graph_diff(actual, expected)[1])}\n"
        f"only expected: {sorted(graph_diff(actual, expected)[2])}"
    )


def skolemised(graph: Graph, root: str) -> Graph:
    """What the session does to blank nodes before it writes (PD-8a)."""
    return graph.skolemize(
        authority="https://example.org", basepath=f"{root}/graph/.well-known/genid/"
    )


@pytest.mark.parametrize("name", list(ROOT_CLASSES))
@DRAWN
@given(data=st.data())
def test_an_aggregate_survives_the_graph_unchanged(name: str, data: st.DataObject) -> None:
    obj = data.draw(aggregate(toy(), name))
    mapper = toy_mapper()
    graph = mapper.to_graph(obj)
    back = mapper.from_graph(
        ROOT_CLASSES[name], obj.id, graph, storage_of(ROOT_CLASSES[name], obj.id)
    )
    assert canonical(back) == canonical(untracked(obj)), "an object differs after the graph"


@DRAWN
@given(data=st.data())
def test_a_graph_with_skolemised_blank_nodes_gives_the_same_object(data: st.DataObject) -> None:
    obj = data.draw(aggregate(toy(), "LibraryAccess"))
    mapper = toy_mapper()
    graph = skolemised(mapper.to_graph(obj), obj.id)
    back = mapper.from_graph(LibraryAccess, obj.id, graph, graph_iri(obj.id))
    assert canonical(back) == canonical(untracked(obj)), "skolem IRIs nest back as owned parts"


@pytest.mark.parametrize("name", list(ROOT_CLASSES))
@DRAWN
@given(data=st.data())
def test_the_graph_is_the_one_the_generated_context_gives(name: str, data: st.DataObject) -> None:
    """Mapper and context agree on predicates, types, enum meanings and references."""
    obj = data.draw(aggregate(toy(), name))
    view = toy_mapper().view
    internal = {
        URIRef(view.get_uri(s, expand=True))
        for c in view.all_classes()
        for s in view.class_induced_slots(c)
        if is_internal(s)
    }
    by_context = Graph().parse(data=rdf_of(toy(), obj, name), format="nt")
    expected = Graph()
    for s, p, o in by_context:
        if p not in v.BOOKKEEPING_PREDICATES:
            expected.add((s, p, o))
    actual = Graph()
    for s, p, o in toy_mapper().to_graph(obj):
        if p not in internal:
            actual.add((s, p, o))
    assert_same_graph(actual, expected)


def test_owned_parts_are_nested_and_typed():
    iri = book_iri(1)
    graph = toy_mapper().to_graph(dune(iri))
    chapters = list(graph.objects(URIRef(iri), URIRef("https://example.org/ns/library#chapter")))
    assert len(chapters) == 2, "each chapter hangs from the root"
    assert all(
        (c, RDF.type, URIRef("http://purl.org/ontology/bibo/Chapter")) in graph for c in chapters
    )
    assert all(str(c).startswith(f"{iri}/parts/") for c in chapters), "minted under the root"
    note = next(graph.objects(chapters[0], URIRef("https://example.org/ns/library#note")))
    assert (note, URIRef("http://schema.org/text"), Literal("a note")) in graph, "notes nest too"


def test_an_enum_is_stored_as_its_meaning_iri_and_read_back_as_its_value():
    iri = book_iri(2)
    mapper = toy_mapper()
    graph = mapper.to_graph(dune(iri))
    assert (URIRef(iri), URIRef(f"{SCHEMA}genre"), URIRef(f"{SCHEMA}Fiction")) in graph
    assert mapper.from_graph(Book, iri, graph, graph_iri(iri)).genre == Genre.FICTION.value


def test_a_reference_to_another_aggregate_is_an_iri_not_a_node_description():
    scan = Scan(id=f"{TENANT}/scans/1", label="Scan", description="d", scan_of=book_iri(3))
    mapper = toy_mapper()
    graph = mapper.to_graph(scan)
    target = URIRef(book_iri(3))
    assert (URIRef(scan.id), URIRef(f"{SCHEMA}exampleOfWork"), target) in graph
    assert (target, RDF.type, None) not in graph, "the referenced book is not described here"
    assert mapper.from_graph(Scan, scan.id, graph, graph_iri(scan.id)).scan_of == book_iri(3)


def test_a_grant_assignee_that_is_an_iri_string_is_written_and_read_as_an_iri():
    """linkml's rdflib_dumper fails on this: the slot ranges over Principal but holds an IRI."""
    access = toy_access(
        grants=[Grant(assignee=ADA, target=TENANT, role="librarian")],
        prohibitions=[Prohibition(assignee=ADA, target=book_iri(1), action=Action.DELETE)],
    )
    mapper = toy_mapper()
    graph = mapper.to_graph(access)
    odrl = "http://www.w3.org/ns/odrl/2/"
    assert (None, URIRef(f"{odrl}assignee"), URIRef(ADA)) in graph, "the assignee is an IRI"
    assert (None, URIRef(f"{odrl}action"), URIRef(f"{odrl}delete")) in graph, (
        "the action is a meaning IRI"
    )
    back = mapper.from_graph(
        LibraryAccess, access.id, skolemised(graph, access.id), graph_iri(access.id)
    )
    assert canonical(back) == canonical(access)


def test_parts_without_an_identifier_are_blank_nodes_that_nest_back_when_skolemised():
    access = toy_access(grants=[Grant(assignee=ADA, target=TENANT, role="librarian")])
    mapper = toy_mapper()
    graph = mapper.to_graph(access)
    grant = next(
        graph.objects(URIRef(access.id), URIRef("https://meaningfy.ws/ns/rdf-persistence#grant"))
    )
    assert isinstance(grant, BNode), "a grant has no identity of its own"
    skolem = skolemised(graph, access.id)
    assert all(not isinstance(n, BNode) for t in skolem for n in t), "nothing is left blank"
    assert (
        mapper.from_graph(LibraryAccess, access.id, skolem, graph_iri(access.id)).grants
        == access.grants
    )


def test_tracking_is_read_from_the_statements_about_the_graph_iri_not_the_root():
    iri = book_iri(4)
    mapper = toy_mapper()
    graph = mapper.to_graph(dune(iri))
    root, about = URIRef(iri), graph_iri(iri)
    graph.add(
        (
            about,
            v.CREATED,
            Literal(
                "2026-11-05T09:00:00+00:00",
                datatype=URIRef("http://www.w3.org/2001/XMLSchema#dateTime"),
            ),
        )
    )
    graph.add((about, v.CREATOR, URIRef(ADA)))
    graph.add((about, v.CONTRIBUTOR, URIRef(f"{ADA}2")))
    graph.add((about, v.VERSION, Literal("v1")))
    graph.add((root, v.CREATOR, URIRef("https://example.org/people/impostor")))
    back = mapper.from_graph(Book, iri, graph, about)
    assert back.creator == ADA, "the creator is the one the graph IRI names"
    assert back.contributor == [f"{ADA}2"], "contributors come from the graph IRI too"
    assert back.created is not None and back.created.year == 2026, "created is a date-time"


def test_the_tenant_root_reads_its_tracking_from_the_meta_graph():
    mapper = toy_mapper()
    library = Library(id=TENANT, label="City library", description="d", city="Brussels")
    graph = mapper.to_graph(library)
    graph.add((meta_graph_iri(TENANT), v.CREATOR, URIRef(ADA)))
    assert mapper.from_graph(Library, TENANT, graph, meta_graph_iri(TENANT)).creator == ADA


def test_tracking_is_not_written_by_the_mapper():
    iri = book_iri(5)
    book = dune(iri).model_copy(update={"creator": ADA, "contributor": [ADA]})
    graph = mapper_graph = toy_mapper().to_graph(book)
    assert not [p for _, p, _ in mapper_graph if p in v.BOOKKEEPING_PREDICATES], str(graph)


def test_a_graph_without_the_root_is_refused():
    with pytest.raises(ValueError, match="no statements"):
        toy_mapper().from_graph(Book, book_iri(6), Graph(), graph_iri(book_iri(6)))


def test_new_part_mints_an_iri_under_the_root_and_keeps_the_fields():
    root = book_iri(7)
    one, two = new_part(Chapter, root, number=1), new_part(Chapter, root, number=1)
    assert one.id.startswith(f"{root}/parts/"), "minted under the root"
    assert one.id != two.id, "each part is fresh"
    assert one.number == 1


def test_a_part_that_arrives_without_an_identifier_cannot_be_built_so_the_helper_is_the_way():
    with pytest.raises(ValueError, match="id"):
        Chapter(number=1)


CHAPTER = URIRef("https://example.org/ns/library#chapter")
NOTE = URIRef("https://example.org/ns/library#note")


@pytest.mark.parametrize(
    ("owner", "predicate"),
    [("root", CHAPTER), ("chapter", NOTE)],
    ids=["on the root", "on a chapter"],
)
def test_a_stored_graph_whose_owned_parts_loop_is_refused_and_not_a_recursion_error(
    owner, predicate
):
    iri = book_iri(7)
    graph = toy_mapper().to_graph(dune(iri))
    first_chapter = next(graph.objects(URIRef(iri), CHAPTER))
    node = URIRef(iri) if owner == "root" else first_chapter
    graph.add((node, predicate, node))
    with pytest.raises(ValueError, match="cycle"):
        toy_mapper().from_graph(Book, iri, graph, graph_iri(iri))
