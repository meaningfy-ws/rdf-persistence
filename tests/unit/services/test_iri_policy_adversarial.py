"""The session, the aggregates service and the tenancy under a flat IRI policy, attacked (iri-policy stage 1).

Probes that expose a gap are kept as ``xfail(strict=True)`` so the suite stays green and the gap
stays visible.
"""

import json

import pytest
from rdflib import URIRef

from rdf_persistence import Action, GrantSet, RdfFormat
from rdf_persistence.domain.exceptions import (
    InvalidBody,
    InvalidGrant,
    InvalidIri,
)
from rdf_persistence.domain.iris import DEFAULT_IRIS, graph_iri
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.aggregates import Aggregates
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import ROLES, direct
from tests.unit.services.test_iri_policy_checks import (
    ADA,
    BASE,
    DOCUMENTS,
    IRIS,
    TENANT,
    TTL,
    StoreTenancy,
    body,
    book,
    chapter_ids,
    create,
    loaded,
    replace,
    session_on,
)

CHAPTER = URIRef("http://purl.org/ontology/bibo/Chapter")
BOOK = URIRef("http://purl.org/ontology/bibo/Book")
OTHER_TENANT = str(IRIS.tenant("q9y7j1n"))


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
def aggregates(store) -> Aggregates:
    return Aggregates(DOCUMENTS, StoreTenancy(store), iris=IRIS)  # type: ignore[arg-type]


async def nothing_reached(store: FakeStore) -> None:
    assert store.sent("update") == [] and store.sent("query") == [], "the store was reached"


# -- IRIs with trailing characters ----------------------------------------------------------------


@pytest.mark.parametrize(
    "suffix", ["/", "#frag", "?q=1", "\n", "/graph", "//", "%20", " "], ids=repr
)
@pytest.mark.parametrize("call", ["add_graph", "get_graph", "load_graph", "remove"])
async def test_an_aggregate_iri_with_a_tail_is_refused_before_the_store(store, suffix, call):
    arguments = {
        "add_graph": ([],),
        "get_graph": (),
        "load_graph": (TTL,),
        "remove": ("v",),
    }[call]
    extra = {"load_graph": {"rdf_format": RdfFormat.NTRIPLES}}.get(call, {})
    with pytest.raises(InvalidIri):
        await getattr(session_on(store), call)(book(1) + suffix, *arguments, **extra)
    await nothing_reached(store)


@pytest.mark.parametrize(
    "who", ["the access record of another tenant", "its meta graph", "a registry"]
)
async def test_the_tenants_bookkeeping_graphs_are_not_aggregates_a_caller_may_commit(store, who):
    iri = {
        "the access record of another tenant": f"{OTHER_TENANT}/access",
        "its meta graph": f"{TENANT}/meta",
        "a registry": f"{TENANT}/registry",
    }[who]
    with pytest.raises(InvalidIri):
        await session_on(store).add_graph(iri, [])
    await nothing_reached(store)


# -- loaded graphs --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "graph",
    [
        URIRef(f"{BASE}q9y7j1n/content/{1:013d}"),
        URIRef(f"{BASE}p4x8k2m/book/{1:013d}"),
        URIRef(f"{BASE}p4x8k2m/content/{1:013d}/"),
        URIRef(f"{BASE}p4x8k2m/content/short"),
        URIRef(f"{BASE}p4x8k2m/content/{1:013d}#x"),
        URIRef(book(1)),
        URIRef(f"{book(1)}/graph"),
        URIRef(f"{TENANT}/registry"),
    ],
    ids=[
        "another tenant's",
        "an aggregate's type",
        "a tail",
        "a short id",
        "a fragment",
        "the aggregate itself",
        "the aggregate's own graph",
        "the registry",
    ],
)
async def test_a_loaded_graph_the_policy_would_not_mint_is_refused_and_nothing_is_sent(
    store, graph
):
    with pytest.raises(InvalidIri):
        await session_on(store).add_graph(book(1), [], loaded_graphs=[graph])
    await nothing_reached(store)


async def test_naming_the_same_loaded_graph_twice_is_not_an_error_and_registers_it_once(store):
    session = session_on(store)
    await session.add_graph(book(1), [], loaded_graphs=[loaded(1), loaded(1)])
    assert (await session._registered_loaded(book(1))) == [loaded(1)]


async def test_a_loaded_graph_of_a_removed_aggregate_is_free_for_another(store):
    session = session_on(store)
    await session.add_graph(book(1), [], loaded_graphs=[loaded(1)])
    _, _, version = await session.get_graph(book(1))
    await session.remove(book(1), version)
    await session.add_graph(book(2), [], loaded_graphs=[loaded(1)])


async def test_a_loaded_graph_an_aggregate_dropped_is_free_for_another(store):
    session = session_on(store)
    await session.add_graph(book(1), [], loaded_graphs=[loaded(1)])
    _, _, version = await session.get_graph(book(1))
    await session.replace_graph(book(1), [], version, loaded_graphs=[])
    await session.add_graph(book(2), [], loaded_graphs=[loaded(1)])


async def test_a_replace_that_names_no_loaded_graphs_keeps_the_registered_ones(store):
    session = session_on(store)
    await session.add_graph(book(1), [], loaded_graphs=[loaded(1)])
    _, _, version = await session.get_graph(book(1))
    await session.replace_graph(book(1), [], version)  # None keeps the registered ones
    assert await session._registered_loaded(book(1)) == [loaded(1)]


# -- bodies under a flat part template ------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="a replace may name {root}/graph as a chapter: the stored subjects include the graph IRI "
    "(its version and creator statements), so the check 'a part this aggregate stores' passes and "
    "the bookkeeping subject becomes a Chapter",
)
async def test_a_chapter_cannot_take_the_iri_of_its_own_graph(aggregates, store):
    iri = await create(aggregates, body({"number": 1}))
    updates = len(store.sent("update"))
    with pytest.raises(InvalidBody):
        await replace(aggregates, iri, body({"id": f"{iri}/graph", "number": 1}))
    assert len(store.sent("update")) == updates, "nothing was written"


def one_book(n: int = 1) -> bytes:
    return body({"number": n})


async def test_a_replace_naming_a_part_of_another_tenant_is_refused(aggregates, store):
    iri = await create(aggregates, one_book())
    foreign = f"{BASE}q9y7j1n/chapter/{1:013d}"
    with pytest.raises(InvalidBody):
        await replace(aggregates, iri, body({"id": foreign, "number": 1}))


@pytest.mark.parametrize(
    "named",
    [
        pytest.param(lambda own, root: root, id="its own root as a chapter"),
        pytest.param(lambda own, root: f"{TENANT}", id="the tenant as a chapter"),
        pytest.param(lambda own, root: f"{TENANT}/access", id="the access record as a chapter"),
        pytest.param(lambda own, root: f"{TENANT}/registry", id="the registry as a chapter"),
        pytest.param(lambda own, root: str(loaded(1)), id="a loaded graph as a chapter"),
        pytest.param(lambda own, root: book(2), id="another aggregate's root as a chapter"),
        pytest.param(lambda own, root: "urn:x:1", id="a foreign IRI as a chapter"),
    ],
)
async def test_a_chapter_cannot_take_the_iri_of_something_that_is_not_a_part(
    aggregates, store, named
):
    iri = await create(aggregates, one_book())
    (own,) = chapter_ids(await aggregates.read(TENANT, ADA, iri))
    updates = len(store.sent("update"))
    with pytest.raises(InvalidBody):
        await replace(aggregates, iri, body({"id": named(own, iri), "number": 1}))
    assert len(store.sent("update")) == updates, "nothing was written"


async def test_two_chapters_that_name_the_same_stored_part_are_one_part_or_refused(aggregates):
    iri = await create(aggregates, one_book())
    (own,) = chapter_ids(await aggregates.read(TENANT, ADA, iri))
    try:
        stored = await replace(
            aggregates, iri, body({"id": own, "number": 1}, {"id": own, "number": 2})
        )
    except InvalidBody:
        return  # refusing the duplicate is as good
    assert chapter_ids(stored) == {own}


async def test_a_new_chapter_with_two_types_is_refused_not_minted_under_a_guess(aggregates, store):
    document = {
        "label": "Dune",
        "description": "A planet.",
        "chapters": [{"@type": ["Chapter", "Book"], "number": 1}],
    }
    with pytest.raises(InvalidBody):
        await create(aggregates, json.dumps(document).encode())
    assert store.sent("update") == []


async def test_a_new_chapter_typed_as_a_root_class_is_refused(aggregates, store):
    document = {
        "label": "Dune",
        "description": "A planet.",
        "chapters": [{"@type": "Book", "label": "x", "description": "y"}],
    }
    with pytest.raises(InvalidBody):
        await create(aggregates, json.dumps(document).encode())
    assert store.sent("update") == []


async def test_a_replace_may_not_move_a_part_between_aggregates_by_naming_it_in_both(aggregates):
    first = await create(aggregates, one_book(1))
    second = await create(aggregates, one_book(2))
    (stolen,) = chapter_ids(await aggregates.read(TENANT, ADA, first))
    with pytest.raises(InvalidBody):
        await replace(aggregates, second, body({"id": stolen, "number": 9}))
    assert chapter_ids(await aggregates.read(TENANT, ADA, first)) == {stolen}


async def test_a_replace_that_drops_a_part_then_another_replace_cannot_take_it_back_by_name(
    aggregates,
):
    iri = await create(aggregates, one_book())
    (gone,) = chapter_ids(await aggregates.read(TENANT, ADA, iri))
    await replace(aggregates, iri, body({"number": 2}))  # the old chapter is dropped
    assert gone not in chapter_ids(await aggregates.read(TENANT, ADA, iri))
    with pytest.raises(InvalidBody):
        await replace(aggregates, iri, body({"id": gone, "number": 1}))


async def test_a_replace_naming_the_stored_part_of_a_deleted_aggregate_is_refused(aggregates):
    first = await create(aggregates, one_book(1))
    second = await create(aggregates, one_book(2))
    (orphan,) = chapter_ids(await aggregates.read(TENANT, ADA, first))
    _, _, version = await aggregates.read(TENANT, ADA, first)
    await aggregates.remove(TENANT, ADA, first, version)
    with pytest.raises(InvalidBody):
        await replace(aggregates, second, body({"id": orphan, "number": 1}))


async def test_the_create_of_a_blank_node_part_mints_beside_the_root_in_the_tenant_by_the_part_type(
    aggregates,
):
    iri = await create(aggregates, body({"number": 1}, {"number": 2}))
    chapters = chapter_ids(await aggregates.read(TENANT, ADA, iri))
    assert len(chapters) == 2
    for chapter in chapters:
        assert chapter.startswith(f"{BASE}p4x8k2m/chapter/") and not chapter.startswith(iri)


# -- with_iris ------------------------------------------------------------------------------------


def test_rules_bound_to_a_policy_leave_the_original_rules_on_the_default_policy():
    original = AccessRules(load_role_definitions(ROLES))
    flat_graph = str(graph_iri(book(1)))
    grants = GrantSet(grants=[direct(Action.MODIFY, flat_graph, str(ADA.id))])
    rebound = original.with_iris(IRIS)
    rebound.validate_grants(grants, TENANT)
    with pytest.raises(InvalidGrant):
        original.validate_grants(grants, TENANT)
    assert rebound is not original and original._iris is DEFAULT_IRIS


def test_rebinding_twice_does_not_stack_and_does_not_reach_back():
    original = AccessRules(load_role_definitions(ROLES))
    first = original.with_iris(IRIS)
    second = first.with_iris(DEFAULT_IRIS)
    assert (original._iris, first._iris, second._iris) == (DEFAULT_IRIS, IRIS, DEFAULT_IRIS)
    assert first._permits is original._permits or first._permits == original._permits
