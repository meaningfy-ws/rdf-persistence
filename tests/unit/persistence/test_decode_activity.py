"""A stored activity decodes into its most specific generated class (aggregate-events 1.4; PD-16; TC-41, TC-42).

The activities are committed through a session over the fake store (served commands for the
Transition and the consumer's subclass), read back with ``Session.activities``, and decoded.
"""

import pytest
from rdflib import RDF, URIRef
from rdflib.namespace import PROV

from rdf_persistence import generated_models
from rdf_persistence.core.domain.generated.rp_provenance import Activity, Add, Remove, Replace
from rdf_persistence.core.domain.generated.rp_workflow import Transition
from rdf_persistence.persistence.services.decoding import decode_activity
from rdf_persistence.provenance.services.provenance import activity_class_named, activity_class_of
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import MODULES, TOY_SCHEMA, ApproveBook, toy_mapper
from tests.unit.services.test_session_activity import B1, B2, B3, book, opened

VIEW = load_schema(TOY_SCHEMA)
MODELS = generated_models(*MODULES)
APPROVE_BOOK = URIRef("https://example.org/ns/library#ApproveBook")
MOVE = "urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c101"
APPROVE = "urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c102"


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


async def stored(store: FakeStore):
    """Every activity of the toy tenant as (iri, graph)."""
    async with opened(store) as session:
        return await session.activities(v.ACTIVITY, RDF.type, v.ACTIVITY)


async def test_tc41_each_stored_activity_decodes_into_its_own_class(store):
    async with opened(store) as session:
        version = await session.add_graph(B1, book(B1))
        await session.replace_graph(B1, book(B1), version)
        await session.add_graph(
            B2,
            book(B2),
            served=toy_mapper().served(Transition(id=MOVE, used_resource=B2)),
        )
        await session.add_graph(
            B3,
            book(B3),
            served=toy_mapper().served(ApproveBook(id=APPROVE, used_resource=B3)),
        )
    decoded = {
        iri: decode_activity(VIEW, MODELS, toy_mapper(), iri, graph)
        for iri, graph in (await stored(store)).items()
    }
    assert {type(a) for a in decoded.values()} == {
        Add,
        Replace,
        Transition,
        ApproveBook,
    }, "each in its own class, none in a parent"
    assert decoded[APPROVE].used_resource == B3, "the subclass keeps its slot"
    assert decoded[MOVE].used_resource == B2, "the transition keeps its slot"


@pytest.mark.parametrize(
    ("types", "expected"),
    [
        ({v.ACTIVITY, v.REMOVE}, Remove),
        ({v.ACTIVITY}, Activity),
        ({PROV.Activity, v.TRANSITION, APPROVE_BOOK}, ApproveBook),
    ],
)
def test_tc42_the_most_specific_class_among_the_types_wins(types, expected):
    assert activity_class_of(VIEW, MODELS, types) is expected, (
        "the most specific class among the types is chosen"
    )


def test_tc42_a_type_of_no_class_of_the_schema_is_a_lookup_error():
    with pytest.raises(LookupError):
        activity_class_of(VIEW, MODELS, {URIRef("https://elsewhere.example/Thing")})
    with pytest.raises(LookupError):
        activity_class_named(VIEW, MODELS, "https://elsewhere.example/Thing")


def test_a_class_named_by_its_iri_is_the_same_as_one_by_its_types():
    assert activity_class_named(VIEW, MODELS, str(APPROVE_BOOK)) is ApproveBook, (
        "a class named by its IRI is the class named by its types"
    )


def test_a_schema_class_that_is_not_an_activity_is_a_lookup_error() -> None:  # D-19
    generation = VIEW.get_uri("Generation", expand=True)
    with pytest.raises(LookupError, match="not an activity"):
        activity_class_named(VIEW, MODELS, generation)
    with pytest.raises(LookupError, match="not an activity"):
        activity_class_of(VIEW, MODELS, {URIRef(generation)})


async def test_a_decode_of_a_class_the_schema_lacks_is_a_lookup_error(store):
    async with opened(store) as session:
        await session.add_graph(B1, book(B1))
    ((iri, graph),) = (await stored(store)).items()
    graph.remove((URIRef(iri), RDF.type, None))
    graph.add((URIRef(iri), RDF.type, URIRef("https://elsewhere.example/Thing")))
    with pytest.raises(LookupError):
        decode_activity(VIEW, MODELS, toy_mapper(), iri, graph)


async def test_a_decode_of_triples_the_class_refuses_is_a_value_error(store):
    async with opened(store) as session:
        await session.add_graph(B1, book(B1))
    ((iri, graph),) = (await stored(store)).items()
    graph.remove((URIRef(iri), v.ACTIVITY_STARTED, None))
    graph.add((URIRef(iri), v.ACTIVITY_STARTED, URIRef("https://elsewhere.example/not-a-time")))
    with pytest.raises(ValueError):
        decode_activity(VIEW, MODELS, toy_mapper(), iri, graph)
