"""What the flat-IRI-policy tests share: the policy, the tenant, a session over the fake store, the body builders."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from rdflib import RDF, URIRef

from rdf_persistence.api.services.aggregates import Aggregates
from rdf_persistence.api.services.documents import Documents
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.media import JSON
from rdf_persistence.iris.services.generated.rp_iris_services import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import iri_types
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import GENERATED, TOY_SCHEMA

BASE = "https://example.org/"
FLAT = "{base}{tenant_id}/{type}/{id}"
ADA = Principal(id="https://example.org/people/ada")
VIEW = load_schema(TOY_SCHEMA)
ROOT_TYPES, OWNED_TYPES = iri_types(VIEW)
TTL = b'<https://e.org/b> <https://e.org/p> "x" .'


def flat_iris() -> Iris:
    policy = IriPolicy(
        tenant_template="{base}library/{tenant_id}",
        aggregate_template=FLAT,
        part_template=FLAT,
        loaded_graph_template=FLAT,
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
        object_id=IdSpec(kind=IdKind.RANDOM, length=13),
    )
    settings = ServiceSettings(
        base=BASE,
        prefix="lib",
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        deployment="k3f9a2x",
        iri_policy=policy,
    )
    return Iris(settings, ROOT_TYPES, OWNED_TYPES)


IRIS = flat_iris()
TENANT = str(IRIS.tenant("p4x8k2m"))
DOCUMENTS = Documents(VIEW, GENERATED, iris=IRIS)
BOOK_CLASS = DOCUMENTS.aggregates["books"]  # the class of the route the aggregates are read through


def book(n: int) -> str:
    return str(IRIS.aggregate(TENANT, "book", "books", f"{n:013d}"))


def loaded(n: int) -> URIRef:
    return URIRef(f"{BASE}p4x8k2m/content/{n:013d}")


def session_on(store: FakeStore) -> Session:
    return Session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=ADA,
        clock=lambda: datetime(2026, 11, 8, tzinfo=UTC),
        iris=IRIS,
    )


class StoreTenancy:
    """What ``Aggregates`` needs of a tenancy: a real session over the fake store."""

    def __init__(self, store: FakeStore) -> None:
        self.store = store

    @asynccontextmanager
    async def tenant_session(self, tenant, principal, *, may_read=None):
        yield session_on(self.store)


def body(*parts: dict) -> bytes:
    return json.dumps(
        {"label": "Dune", "description": "A planet.", "chapters": list(parts)}
    ).encode()


async def create(aggregates: Aggregates, data: bytes) -> str:
    iri, _ = await aggregates.create(
        TENANT, ADA, DOCUMENTS.aggregates["books"], "books", data, JSON
    )
    return iri


async def replace(aggregates: Aggregates, iri: str, data: bytes):
    _, _, version = await aggregates.read(TENANT, ADA, iri, BOOK_CLASS)
    return await aggregates.replace(
        TENANT, ADA, DOCUMENTS.aggregates["books"], iri, data, JSON, version
    )


def chapter_ids(stored) -> set[str]:
    graph = stored[0]
    return {
        str(s) for s in graph.subjects(RDF.type, URIRef("http://purl.org/ontology/bibo/Chapter"))
    }
