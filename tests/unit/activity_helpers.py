"""The helpers of the tests of the activity a commit records: a session on the fake store, the activities
it stored, the books they touched and the toy schema's round trip.

The session, tenancy, provenance, persistence and messaging tests use them, from more than one theme,
so they sit at the root of the unit tests.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from functools import cache

from rdflib import RDF, Graph, Literal, URIRef

from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity, Add, Remove, Replace
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import aggregate_keys
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from rdf_persistence_generation.testkit.conformance import Conformance
from rdf_persistence_generation.testkit.roundtrip import without_framing
from tests.toy import ADA, TENANT, TOY_SCHEMA, book_iri, dune, toy_mapper

B1, B2, B3 = (book_iri(n) for n in (1, 2, 3))
PROVENANCE = DEFAULT_IRIS.provenance(TENANT)
BOOK_CLASS = "http://purl.org/ontology/bibo/Book"
SHELF_CLASS = "https://example.org/ns/library#Shelf"
ADA_PRINCIPAL = Principal(id=ADA)
ACTIVITY_CLASSES = {v.ADD: Add, v.REPLACE: Replace, v.REMOVE: Remove}
X = "urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c001"
KEYS = aggregate_keys(load_schema(TOY_SCHEMA))
BIBO = "http://purl.org/ontology/bibo/"
BOOK, ISBN = URIRef(BIBO + "Book"), URIRef(BIBO + "isbn")
TITLE = URIRef("http://purl.org/dc/terms/title")


def ticking() -> Callable[[], datetime]:
    """A clock that is one second later at every reading."""
    now = [datetime(2026, 11, 14, 10, 0, tzinfo=UTC)]

    def clock() -> datetime:
        now[0] += timedelta(seconds=1)
        return now[0]

    return clock


def opened(store: FakeStore, **keywords) -> AbstractAsyncContextManager[Session]:
    return fake_session(
        store,
        tenant_iri=TENANT,
        principal=ADA_PRINCIPAL,
        clock=keywords.pop("clock", ticking()),
        **keywords,
    )


async def stored_graph(store: FakeStore, graph: URIRef, database: str = FAKE_DATABASE) -> Graph:
    text = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"
    return (await store.query(database, text)).graph or Graph()


async def activities(
    store: FakeStore, graph: URIRef = PROVENANCE, database: str = FAKE_DATABASE
) -> list[Activity]:
    """The activities of a provenance graph, decoded through the mapper, in start order."""
    stored = await stored_graph(store, graph, database)
    found = []
    for subject in set(stored.subjects(RDF.type, v.ACTIVITY)):
        types = set(stored.objects(subject, RDF.type))
        cls = next((ACTIVITY_CLASSES[t] for t in types if t in ACTIVITY_CLASSES), Activity)
        found.append(toy_mapper().from_graph(cls, str(subject), stored, graph))
    return sorted(found, key=lambda a: (a.started_at_time, a.id))


def events(parts) -> list[tuple]:
    return sorted((p.entity, p.entity_class, p.entity_version) for p in parts or [])


def book(iri: str) -> list:
    return list(toy_mapper().to_triples(dune(iri)))


def isbn_book(iri: str, *isbns: str | Literal, title: str | None = None) -> list:
    """The triples of a book root holding ``isbns``; none gives a book without ISBN."""
    root = URIRef(iri)
    return [
        (root, RDF.type, BOOK),
        *((root, ISBN, i if isinstance(i, Literal) else Literal(i)) for i in isbns),
        *(((root, TITLE, Literal(title)),) if title else ()),
    ]


async def only_activity(store: FakeStore) -> Activity:
    found = await activities(store)
    assert len(found) == 1, f"one activity, found {len(found)}"
    return found[0]


class Hook:
    """An ``on_commit`` that keeps what it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[Activity, Session]] = []

    async def __call__(self, activity: Activity, session: Session) -> None:
        self.calls.append((activity, session))


async def overtaken_commit(store, **options):
    """A commit of two replaces; another writer changes one of the two graphs before the ASK, so the
    commit applied and the call returns (PD-4)."""
    async with opened(store, **options) as session, opened(store) as other:
        v1 = await session.add_graph(B1, book(B1))
        v2 = await session.add_graph(B2, book(B2))

        async def overtake() -> None:
            store.after_update = None
            _, _, current = await other.get_graph(B1)
            await other.replace_graph(B1, book(B1), current)

        store.after_update = overtake
        async with session.transaction() as transaction:
            await transaction.replace_graph(B1, book(B1), v1)
            await transaction.replace_graph(B2, book(B2), v2)


@cache
def toy() -> Conformance:
    return Conformance.of(TOY_SCHEMA)


def mapped(model: Activity) -> Graph:
    """The mapper's graph: the activity's own class only, without the ancestor types the session adds (TC-11)."""
    return toy_mapper().to_graph(model)


def unordered[M: Activity](model: M) -> M:
    """``model`` with its parts in the order of ``(entity, entity_version)``: RDF keeps no order (PD-4)."""

    def order(parts):
        return sorted(parts, key=lambda p: (p.entity, p.entity_version)) if parts else parts

    return model.model_copy(
        update={
            "generations": order(model.generations),
            "invalidations": order(model.invalidations),
            "was_associated_with": sorted(model.was_associated_with or []) or None,
        }
    )


def framed(model: Activity) -> dict:
    name = type(model).__name__
    body = without_framing(toy().documents.frame(mapped(model), toy().view.get_class(name)))
    assert isinstance(body, dict), "one activity is one object"
    return body


def with_class_iris_expanded(body: dict) -> dict:
    """``body`` with the compact IRI of each ``entity_class`` written out, with the context's prefixes.

    Compaction writes a value of an ``@id`` term as ``lib:Book`` when the context has the prefix ``lib``.
    """
    prefixes = toy().documents.context
    parts = ("generations", "invalidations")

    def expanded(part: dict) -> dict:
        prefix, _, rest = part.get("entity_class", "").partition(":")
        if prefix not in prefixes or not rest:
            return part
        return {**part, "entity_class": f"{prefixes[prefix]}{rest}"}

    return {**body, **{p: [expanded(x) for x in body[p]] for p in parts if p in body}}
