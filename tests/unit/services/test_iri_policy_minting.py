"""Roots, parts and loaded graphs are minted through ``Iris`` (iri-policy task 3.2, PD-3, PD-3a, PD-7a).

The check that a body's parts sit inside the aggregate is the default's nested rule; the flat rule
replaces it in task 3.3, so a flat part template is exercised here only where that check is not reached.
"""

import json
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import new_part
from rdf_persistence.domain.exceptions import InvalidBody, InvalidIri
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import Iris
from rdf_persistence.domain.media import JSON, JSON_LD
from rdf_persistence.services.aggregates import Aggregates
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.generated.books import Chapter
from tests.toy import TENANT, TOY_SCHEMA, book_iri
from tests.unit.services.conftest import GENERATED

BASE = "http://mwb.meaningfy.ws/"
FLAT = "{base}{tenant_id}/{type}/{id}"
OBJECT_ID = "[a-z0-9]{13}"
ADA = Principal(id="https://example.org/people/ada")
VIEW = load_schema(TOY_SCHEMA)
ROOT_TYPES, OWNED_TYPES = iri_types(VIEW)
BOOK_TYPE = "http://purl.org/ontology/bibo/Book"
CHAPTER_TYPE = "http://purl.org/ontology/bibo/Chapter"


def settings(
    tenant_template: str = "{base}project/{tenant_id}", part: str = FLAT
) -> ServiceSettings:
    return ServiceSettings(
        base=BASE,
        prefix="mwb",
        tenant_segment="projects",
        creator_role="owner",
        roles_claim="roles",
        deployment="k3f9a2x",
        iri_policy=IriPolicy(
            tenant_template=tenant_template,
            aggregate_template=FLAT,
            part_template=part,
            loaded_graph_template=FLAT,
            tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
            object_id=IdSpec(kind=IdKind.RANDOM, length=13),
        ),
    )


def policy(**kwargs) -> Iris:
    return Iris(settings(**kwargs), ROOT_TYPES, OWNED_TYPES)


FLAT_IRIS = policy()
FLAT_TENANT = str(FLAT_IRIS.tenant("p4x8k2m"))
FLAT_DOCUMENTS = Documents(VIEW, GENERATED, iris=FLAT_IRIS)
# parts below the root but by type: the flat template's {type}, with the nested rule still to pass
TYPED = policy(part="{root}/{type}/{id}")
TYPED_DOCUMENTS = Documents(VIEW, GENERATED, iris=TYPED)
DEFAULT_DOCUMENTS = Documents(VIEW, GENERATED)


class RecordingSession:
    """What ``Aggregates`` needs of a session, keeping the graph it was given."""

    def __init__(self) -> None:
        self.added: dict[str, list] = {}

    async def add_graph(self, iri, triples):
        self.added[iri] = list(triples)

    async def get_graph(self, iri):
        return self.added[iri], URIRef(f"{iri}/graph"), "v1"


class RecordingTenancy:
    def __init__(self) -> None:
        self.session = RecordingSession()

    @asynccontextmanager
    async def tenant_session(self, tenant, principal):
        yield self.session


def encoded(body: object) -> bytes:
    return json.dumps(body).encode()


async def created(
    documents: Documents,
    iris: Iris | None,
    tenant: str,
    rp_path: str = "books",
    body: dict | None = None,
):
    tenancy = RecordingTenancy()
    aggregates = Aggregates(documents, tenancy, iris=iris)  # type: ignore[arg-type]
    given = body if body is not None else {"label": "Dune", "description": "A planet."}
    iri, _ = await aggregates.create(
        tenant, ADA, documents.aggregates["books"], rp_path, encoded(given), JSON
    )
    return iri, tenancy.session.added[iri]


# -- "a flat object": root, part and loaded graph, none nested under another ------------------------


async def test_a_flat_root_is_minted_under_the_tenant_by_its_class_type():
    iri, _ = await created(FLAT_DOCUMENTS, FLAT_IRIS, FLAT_TENANT)
    assert re.fullmatch(f"http://mwb\\.meaningfy\\.ws/p4x8k2m/book/{OBJECT_ID}", iri)


def test_a_flat_part_is_minted_beside_the_root_not_under_it():
    root = str(FLAT_IRIS.aggregate(FLAT_TENANT, "book", "books", "a" * 13))
    part = new_part(Chapter, root, iris=FLAT_IRIS, tenant=FLAT_TENANT, number=1)
    assert re.fullmatch(f"http://mwb\\.meaningfy\\.ws/p4x8k2m/chapter/{OBJECT_ID}", part.id)


async def test_a_flat_loaded_graph_is_minted_under_the_tenant_as_content():
    # the tenant sits above every flat IRI, which the session still needs to accept an aggregate (task 3.3)
    iris = policy(tenant_template="{base}{tenant_id}")
    tenant = str(iris.tenant("p4x8k2m"))
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    session = Session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=tenant,
        principal=ADA,
        clock=lambda: datetime(2026, 11, 8, tzinfo=UTC),
        iris=iris,
    )
    loaded = await session.load_graph(
        f"{tenant}/book/{'a' * 13}",
        b'<https://e.org/b> <https://e.org/p> "x" .',
        rdf_format=RdfFormat.NTRIPLES,
    )
    assert re.fullmatch(f"http://mwb\\.meaningfy\\.ws/p4x8k2m/content/{OBJECT_ID}", str(loaded))


async def test_a_part_of_a_body_is_minted_by_the_class_its_type_names():
    body = {
        "label": "Dune",
        "description": "A planet.",
        "chapters": [{"number": 1, "notes": [{"label": "n", "description": "d", "text": "t"}]}],
    }
    iri, triples = await created(TYPED_DOCUMENTS, TYPED, FLAT_TENANT, body=body)
    parts = {str(s) for s, p, _ in triples if p == RDF.type and str(s) != iri}
    assert {
        re.fullmatch(f"{re.escape(iri)}/(chapter|note)/{OBJECT_ID}", s) is not None for s in parts
    } == {True}
    assert sorted(s.split("/")[-2] for s in parts) == ["chapter", "note"]


# -- "the API path changes, the IRIs do not" -------------------------------------------------------


@pytest.mark.parametrize("rp_path", ["files", "ontology-files"])
async def test_the_api_path_does_not_change_the_type_segment_of_the_iris(rp_path):
    iri, _ = await created(FLAT_DOCUMENTS, FLAT_IRIS, FLAT_TENANT, rp_path=rp_path)
    assert iri.split("/")[-2] == "book"


async def test_under_the_default_policy_the_api_path_is_the_segment_and_parts_are_nested():
    body = {"label": "Dune", "description": "A planet.", "chapters": [{"number": 1}]}
    iri, triples = await created(DEFAULT_DOCUMENTS, None, TENANT, rp_path="files", body=body)
    assert iri.startswith(f"{TENANT}/files/")
    (part,) = {str(s) for s, p, _ in triples if p == RDF.type and str(s) != iri}
    assert part.startswith(f"{iri}/parts/")


# -- PD-7a: the type of a new part ---------------------------------------------------------------------


def ld(part: dict) -> bytes:
    return encoded(
        {
            "@context": FLAT_DOCUMENTS.context,
            "@type": BOOK_TYPE,
            "label": "Dune",
            "description": "A planet.",
            "chapters": [part],
        }
    )


async def parsed(documents: Documents, part: dict, root: str, tenant: str):
    return await documents.parse(
        ld(part), JSON_LD, documents.aggregates["books"], root, creating=False, tenant=tenant
    )


FLAT_ROOT = f"{BASE}p4x8k2m/book/{'a' * 13}"


# A blank node with no type is never named: the check that every node is typed refuses it, as it
# always did, whatever the template. A node typed with a class that is not an owned one is named, so
# the template's {type} must refuse it.
async def test_a_typeless_part_is_refused_whatever_the_template():
    for documents, root, tenant in (
        (FLAT_DOCUMENTS, FLAT_ROOT, FLAT_TENANT),
        (DEFAULT_DOCUMENTS, book_iri(1), TENANT),
    ):
        with pytest.raises(InvalidBody, match="wrong type"):
            await parsed(documents, {"number": 1}, root, tenant)


async def test_a_part_of_a_class_that_is_not_owned_is_refused_when_the_template_needs_a_type():
    with pytest.raises(InvalidBody, match="needs a type that is an owned class"):
        await parsed(FLAT_DOCUMENTS, {"@type": BOOK_TYPE, "number": 1}, FLAT_ROOT, FLAT_TENANT)


async def test_under_the_default_template_that_part_is_refused_as_before():
    with pytest.raises(InvalidBody, match="wrong type"):
        await parsed(DEFAULT_DOCUMENTS, {"@type": BOOK_TYPE, "number": 1}, book_iri(1), TENANT)


async def test_a_typed_part_is_named_by_its_class():
    root = f"{BASE}p4x8k2m/book/{'a' * 13}"
    graph = await parsed(TYPED_DOCUMENTS, {"@type": CHAPTER_TYPE, "number": 1}, root, FLAT_TENANT)
    (chapter,) = graph.subjects(RDF.type, URIRef(CHAPTER_TYPE))
    assert re.fullmatch(f"{root}/chapter/{OBJECT_ID}", str(chapter))


# -- new_part --------------------------------------------------------------------------------------


def test_new_part_without_a_policy_mints_under_the_root_as_before():
    root = book_iri(7)
    assert new_part(Chapter, root, number=1).id.startswith(f"{root}/parts/")


def test_new_part_with_a_policy_keeps_the_fields():
    part = new_part(Chapter, "irrelevant", iris=FLAT_IRIS, tenant=FLAT_TENANT, number=3)
    assert part.number == 3


def test_new_part_of_a_class_the_policy_does_not_own_is_refused():
    iris = Iris(settings(), ROOT_TYPES, frozenset())
    with pytest.raises(InvalidIri):
        new_part(Chapter, "irrelevant", iris=iris, tenant=FLAT_TENANT, number=1)
