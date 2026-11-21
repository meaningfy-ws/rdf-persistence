"""Sessions, clocks and book graphs on a real Fuseki, shared by the integration store tests and the store budgets."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from rdflib import RDF, Graph, Literal, URIRef

from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.persistence.adapters.fuseki import FusekiStore
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import aggregate_keys
from tests.toy import TOY_SCHEMA

TENANT = "https://example.org/libraries/6f1c0c1e"
TITLE = URIRef("http://purl.org/dc/terms/title")
START = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
ADA, BEN, CY = (Principal(id=f"https://example.org/people/{n}") for n in ("ada", "ben", "cy"))
BIBO = "http://purl.org/ontology/bibo/"
BOOK, ISBN = URIRef(BIBO + "Book"), URIRef(BIBO + "isbn")
KEYS = aggregate_keys(load_schema(TOY_SCHEMA))


class Ticker:
    """A clock that moves one minute on each reading and keeps the readings it gave."""

    def __init__(self) -> None:
        self.now = START
        self.readings: list[datetime] = []

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        self.readings.append(self.now)
        return self.now

    @property
    def tracked(self) -> datetime:
        """The last commit's tracking time: a recording commit reads the clock once more, for its activity's end."""
        return self.readings[-2]


def book(n: int) -> str:
    """The IRI of the n-th book of the toy tenant."""
    return f"{TENANT}/books/{UUID(int=n)}"


def keyed_book(iri: str, isbn: str | Literal) -> list:
    """The triples of a book of ``iri`` with an ISBN, the key the toy schema makes unique."""
    root = URIRef(iri)
    return [
        (root, RDF.type, BOOK),
        (root, ISBN, isbn if isinstance(isbn, Literal) else Literal(isbn)),
    ]


def title(root: str, text: str) -> list:
    """The one triple that gives the book at ``root`` its title."""
    return [(URIRef(root), TITLE, Literal(text))]


def graph_of(triples: list) -> Graph:
    """A graph holding exactly ``triples``."""
    graph = Graph()
    for triple in triples:
        graph.add(triple)
    return graph


def session_for(store, database, principal=ADA, clock=None) -> Session:
    """A session of the toy tenant on ``database``, as ``principal``, on a ticking clock unless given one."""
    return Session(
        store, database=database, tenant_iri=TENANT, principal=principal, clock=clock or Ticker()
    )


def session_of(store: FusekiStore, database: str, principal: Principal = ADA, keys=KEYS) -> Session:
    """A session as ``session_for`` makes, with the toy schema's unique keys (or ``keys``)."""
    return Session(
        store,
        database=database,
        tenant_iri=TENANT,
        principal=principal,
        clock=Ticker(),
        keys=keys,
    )
