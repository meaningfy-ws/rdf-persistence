"""Checks and ownership go through ``Iris`` (iri-policy task 3.3, PD-4, PD-7, PD-11).

Under the flat policy a root, a part and a loaded graph are all minted beside each other under the
tenant's id, so no check can walk IRI parents: the session matches the policy's templates, the
registry says who owns a loaded graph, and a body may name only the parts its aggregate stores.
"""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import Action, GrantSet
from rdf_persistence.domain.exceptions import InvalidBody, InvalidGrant, InvalidIri
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import Iris, graph_iri
from rdf_persistence.domain.media import JSON
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.aggregates import Aggregates
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import ROLES, TOY_SCHEMA, direct
from tests.unit.services.conftest import GENERATED

BASE = "http://mwb.meaningfy.ws/"
FLAT = "{base}{tenant_id}/{type}/{id}"
ADA = Principal(id="https://example.org/people/ada")
VIEW = load_schema(TOY_SCHEMA)
ROOT_TYPES, OWNED_TYPES = iri_types(VIEW)
TTL = b'<https://e.org/b> <https://e.org/p> "x" .'


def flat_iris() -> Iris:
    policy = IriPolicy(
        tenant_template="{base}project/{tenant_id}",
        aggregate_template=FLAT,
        part_template=FLAT,
        loaded_graph_template=FLAT,
        tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
        object_id=IdSpec(kind=IdKind.RANDOM, length=13),
    )
    settings = ServiceSettings(
        base=BASE,
        prefix="mwb",
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


def book(n: int) -> str:
    return str(IRIS.aggregate(TENANT, "book", "books", f"{n:013d}"))


def loaded(n: int) -> URIRef:
    return URIRef(f"{BASE}p4x8k2m/content/{n:013d}")


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


def session_on(store: FakeStore) -> Session:
    return Session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=ADA,
        clock=lambda: datetime(2026, 11, 8, tzinfo=UTC),
        iris=IRIS,
    )


# -- "a hand-made IRI", "an aggregate IRI with a part's type" -------------------------------------


@pytest.mark.parametrize(
    "iri",
    [
        f"{TENANT}/books/hand-made",
        f"{BASE}p4x8k2m/book/short",
        f"{BASE}p4x8k2m/chapter/{1:013d}",
        f"{BASE}p4x8k2m/content/{1:013d}",
        f"{BASE}q9y7j1n/book/{1:013d}",
    ],
    ids=["hand-made", "short id", "a part's type", "the loaded type", "another tenant"],
)
@pytest.mark.parametrize("call", ["add_graph", "replace_graph", "get_graph"])
async def test_an_iri_the_policy_would_not_mint_is_refused_and_nothing_is_sent(store, iri, call):
    session = session_on(store)
    arguments = {"add_graph": ([],), "replace_graph": ([], "v"), "get_graph": ()}[call]
    with pytest.raises(InvalidIri):
        await getattr(session, call)(iri, *arguments)
    assert store.sent("update") == [] and store.sent("query") == [], "the store was not reached"


async def test_a_flat_aggregate_is_accepted_though_it_is_not_under_the_tenant_iri(store):
    iri = book(1)
    assert not iri.startswith(f"{TENANT}/"), "the premise: flat objects are beside the tenant"
    await session_on(store).add_graph(iri, [])


# -- "a loaded graph of another aggregate" --------------------------------------------------------


async def test_a_loaded_graph_another_aggregate_owns_is_refused_and_nothing_is_written(store):
    session = session_on(store)
    await session.add_graph(book(1), [], loaded_graphs=[loaded(1)])
    updates = len(store.sent("update"))
    with pytest.raises(InvalidIri, match="owned by another aggregate"):
        await session.add_graph(book(2), [], loaded_graphs=[loaded(1)])
    assert len(store.sent("update")) == updates, "no update was sent"


async def test_a_replace_naming_a_loaded_graph_of_another_aggregate_is_refused(store):
    session = session_on(store)
    await session.add_graph(book(1), [], loaded_graphs=[loaded(1)])
    await session.add_graph(book(2), [])
    _, _, version = await session.get_graph(book(2))
    updates = len(store.sent("update"))
    with pytest.raises(InvalidIri):
        await session.replace_graph(book(2), [], version, loaded_graphs=[loaded(1)])
    assert len(store.sent("update")) == updates, "no update was sent"


async def test_the_aggregate_that_owns_a_loaded_graph_may_keep_naming_it(store):
    session = session_on(store)
    await session.add_graph(book(1), [], loaded_graphs=[loaded(1)])
    _, _, version = await session.get_graph(book(1))
    await session.replace_graph(book(1), [], version, loaded_graphs=[loaded(1)])


async def test_a_session_without_loaded_graphs_asks_the_registry_nothing(store):
    session = session_on(store)
    await session.add_graph(book(1), [])
    assert len(store.sent("query")) == 1, "only the confirming ASK for the version token"


# -- "a flat object" end to end -------------------------------------------------------------------


async def test_a_loaded_graph_is_minted_flat_and_registered_by_the_next_commit(store):
    session = session_on(store)
    graph = await session.load_graph(book(1), TTL, rdf_format=RdfFormat.NTRIPLES)
    assert str(graph).startswith(f"{BASE}p4x8k2m/content/")
    await session.add_graph(book(1), [], loaded_graphs=[graph])
    with pytest.raises(InvalidIri):
        await session.add_graph(book(2), [], loaded_graphs=[graph])


# -- "a body that names another aggregate's part" -------------------------------------------------


class StoreTenancy:
    """What ``Aggregates`` needs of a tenancy: a real session over the fake store."""

    def __init__(self, store: FakeStore) -> None:
        self.store = store

    @asynccontextmanager
    async def tenant_session(self, tenant, principal):
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
    _, _, version = await aggregates.read(TENANT, ADA, iri)
    return await aggregates.replace(
        TENANT, ADA, DOCUMENTS.aggregates["books"], iri, data, JSON, version
    )


@pytest.fixture
def aggregates(store) -> Aggregates:
    return Aggregates(DOCUMENTS, StoreTenancy(store), iris=IRIS)  # type: ignore[arg-type]


def chapter_ids(stored) -> set[str]:
    graph = stored[0]
    return {
        str(s) for s in graph.subjects(RDF.type, URIRef("http://purl.org/ontology/bibo/Chapter"))
    }


async def test_a_create_naming_a_part_is_refused_and_nothing_is_written(aggregates, store):
    with pytest.raises(InvalidBody, match="cannot name its parts"):
        await create(aggregates, body({"id": f"{BASE}p4x8k2m/chapter/{9:013d}", "number": 1}))
    assert store.sent("update") == [], "nothing was written"


async def test_a_replace_naming_a_part_of_another_aggregate_is_refused_and_nothing_is_written(
    aggregates, store
):
    first = await create(aggregates, body({"number": 1}))
    second = await create(aggregates, body({"number": 1}))
    foreign = next(iter(chapter_ids(await aggregates.read(TENANT, ADA, second))))
    updates = len(store.sent("update"))
    with pytest.raises(InvalidBody, match="is not a part of the aggregate"):
        await replace(aggregates, first, body({"id": foreign, "number": 1}))
    assert len(store.sent("update")) == updates, "nothing was written"


async def test_a_replace_naming_a_part_the_aggregate_already_stores_is_accepted(aggregates):
    iri = await create(aggregates, body({"number": 1}))
    (own,) = chapter_ids(await aggregates.read(TENANT, ADA, iri))
    stored = await replace(aggregates, iri, body({"id": own, "number": 2}))
    assert chapter_ids(stored) == {own}, "the part keeps its IRI"


async def test_a_replace_may_add_a_part_without_naming_it(aggregates):
    iri = await create(aggregates, body({"number": 1}))
    (own,) = chapter_ids(await aggregates.read(TENANT, ADA, iri))
    stored = await replace(aggregates, iri, body({"id": own, "number": 1}, {"number": 2}))
    assert len(chapter_ids(stored)) == 2 and own in chapter_ids(stored)


# -- the part rule of the default policy stays nested ---------------------------------------------


async def test_the_default_policy_still_accepts_a_part_a_client_names_under_the_root():
    documents = Documents(VIEW, GENERATED)
    root = URIRef(
        "https://example.org/libraries/6f1c0c1e/books/00000000-0000-4000-8000-000000000001"
    )
    given = json.dumps(
        {
            "label": "Dune",
            "description": "A planet.",
            "chapters": [{"id": f"{root}/mine", "number": 1}],
        }
    ).encode()
    graph, named = await documents.parse(
        given, JSON, documents.aggregates["books"], str(root), creating=False
    )
    assert (
        URIRef(f"{root}/mine"),
        RDF.type,
        URIRef("http://purl.org/ontology/bibo/Chapter"),
    ) in graph
    assert named == set(), "the nested rule has nothing to track"


# -- PD-11: grant targets -------------------------------------------------------------------------


def rules() -> AccessRules:
    return AccessRules(load_role_definitions(ROLES), iris=IRIS)


def test_a_grant_on_the_graph_of_a_flat_aggregate_validates():
    rules().validate_grants(
        GrantSet(grants=[direct(Action.MODIFY, str(graph_iri(book(1))), str(ADA.id))]), TENANT
    )


@pytest.mark.parametrize(
    "target",
    [f"{TENANT}/graph", f"{BASE}p4x8k2m/chapter/{1:013d}/graph", f"{BASE}p4x8k2m/book/{1:013d}"],
    ids=["the tenant's own graph", "a part's graph", "a root that is not its graph"],
)
def test_a_grant_on_what_is_not_an_aggregate_graph_is_refused(target):
    with pytest.raises(InvalidGrant):
        rules().validate_grants(
            GrantSet(grants=[direct(Action.MODIFY, target, str(ADA.id))]), TENANT
        )


def test_the_check_scopes_a_flat_aggregate_by_its_graph():
    from rdf_persistence.domain.exceptions import NotFound
    from tests.toy import caller, held

    graph = str(graph_iri(book(1)))
    access = held(direct(Action.READ, graph, str(ADA.id))).model_copy(update={"tenant": TENANT})
    rules().require(caller(principal=str(ADA.id)), access, book(1), Action.READ)
    with pytest.raises(NotFound):
        rules().require(caller(principal=str(ADA.id)), access, book(2), Action.READ)
