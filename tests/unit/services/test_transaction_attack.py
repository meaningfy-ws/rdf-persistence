"""Adversarial tests of ``Session.transaction`` (atomic-commit 1.2): edge cases, bad input, races, limits.

A and B are stored books of the toy tenant, C and D new ones; "another session" is a second session on
the same fake store. Each test names the design.md item it holds the code to (PD-n, Error matrix).
"""

import re
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

import pytest
from rdflib import Literal, URIRef

from rdf_persistence.domain.exceptions import Conflict, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.session import Session
from rdf_persistence.services.tenant_sweep import _registry_view
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import TENANT, book_iri, graph_of

A, B, C, D = (book_iri(n) for n in (1, 2, 3, 4))
TITLE = URIRef("http://purl.org/dc/terms/title")
LOADED_TTL = '<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'
HAS_TRIPLES = "ASK { GRAPH $g { ?s ?p ?o } }"
ANY_MARKER = "ASK { GRAPH $registry { ?m a $marker } }"
ENTRY = "ASK { GRAPH $registry { $graph ?p ?o } }"
URN_MARKER = re.compile(r"urn:uuid:[0-9a-f-]{36}")


def title(iri: str, text: str) -> list:
    return [(URIRef(iri), TITLE, Literal(text))]


def opened(store: FakeStore, who: str) -> AbstractAsyncContextManager[Session]:
    return fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=f"https://example.org/people/{who}"),
        clock=lambda: datetime(2026, 11, 13, tzinfo=UTC),
    )


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with opened(store, "ada") as s:
        yield s


@pytest.fixture
async def other(store) -> AsyncIterator[Session]:
    async with opened(store, "ben") as s:
        yield s


@pytest.fixture
async def seeded(session) -> dict[str, str]:
    """A and B stored, at the returned versions."""
    return {iri: await session.add_graph(iri, title(iri, "first")) for iri in (A, B)}


async def ask(store: FakeStore, text: str, **terms) -> bool:
    return bool((await store.query(FAKE_DATABASE, fill(text, **terms))).askAnswer)


async def stored_title(session: Session, iri: str) -> str:
    graph, _, _ = await session.get_graph(iri)
    return str(graph.value(URIRef(iri), TITLE))


async def stored(session: Session, iri: str) -> bool:
    try:
        await session.get_graph(iri)
    except NotFound:
        return False
    return True


async def has_triples(store: FakeStore, graph: URIRef) -> bool:
    return await ask(store, HAS_TRIPLES, g=term(graph))


async def a_marker_is_left(store: FakeStore) -> bool:
    return await ask(
        store,
        ANY_MARKER,
        registry=term(DEFAULT_IRIS.registry(TENANT)),
        marker=term(v.COMMIT_MARKER),
    )


# -- many changes in one request ----------------------------------------------------------------


async def test_twelve_mixed_changes_commit_in_one_request(store, session):
    keep = [book_iri(100 + n) for n in range(4)]
    drop = [book_iri(200 + n) for n in range(4)]
    new = [book_iri(300 + n) for n in range(4)]
    versions = {iri: await session.add_graph(iri, title(iri, "first")) for iri in (*keep, *drop)}
    sent = len(store.sent("update"))
    async with session.transaction() as t:
        for iri in keep:
            await t.replace_graph(iri, title(iri, "second"), versions[iri])
        for iri in drop:
            await t.remove(iri, versions[iri])
        for iri in new:
            await t.add_graph(iri, title(iri, "new"))
    assert len(store.sent("update")) == sent + 1, "one request for twelve changes"
    assert [await stored_title(session, i) for i in keep] == ["second"] * 4
    assert [await stored(session, i) for i in drop] == [False] * 4
    assert [await stored_title(session, i) for i in new] == ["new"] * 4
    assert not await a_marker_is_left(store)


async def test_one_stale_root_among_twelve_changes_nothing(store, session, other):
    keep = [book_iri(100 + n) for n in range(4)]
    drop = [book_iri(200 + n) for n in range(4)]
    new = [book_iri(300 + n) for n in range(4)]
    versions = {iri: await session.add_graph(iri, title(iri, "first")) for iri in (*keep, *drop)}
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            for iri in keep:
                await t.replace_graph(iri, title(iri, "second"), versions[iri])
            for iri in drop:
                await t.remove(iri, versions[iri])
            for iri in new:
                await t.add_graph(iri, title(iri, "new"))
            await other.replace_graph(drop[3], title(drop[3], "theirs"), versions[drop[3]])
    assert refused.value.iris == (drop[3],)
    assert [await stored_title(session, i) for i in keep] == ["first"] * 4
    assert [await stored(session, i) for i in drop] == [True] * 4
    assert [await stored(session, i) for i in new] == [False] * 4
    assert not await a_marker_is_left(store)


async def test_fifteen_replaced_roots_commit_on_the_fake_store(session):
    roots = [book_iri(600 + n) for n in range(15)]
    versions = {iri: await session.add_graph(iri, title(iri, "first")) for iri in roots}
    async with session.transaction() as t:
        for iri in roots:
            await t.replace_graph(iri, title(iri, "second"), versions[iri])
    assert [await stored_title(session, i) for i in roots] == ["second"] * 15


# -- guards of one kind do not join -------------------------------------------------------------


async def test_two_adds_where_only_one_exists_name_only_that_one_and_write_neither(
    session, other, seeded
):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.add_graph(C, title(C, "new"))
            await t.add_graph(D, title(D, "new"))
            await other.add_graph(D, title(D, "theirs"))
    assert refused.value.iris == (D,)
    assert not await stored(session, C)
    assert await stored_title(session, D) == "theirs"


async def test_every_existing_added_root_is_named_sorted(session, other, seeded):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.add_graph(D, title(D, "new"))
            await t.add_graph(C, title(C, "new"))
            await other.add_graph(C, title(C, "theirs"))
            await other.add_graph(D, title(D, "theirs"))
    assert refused.value.iris == (C, D)
    assert "already exists" in str(refused.value)


async def test_adds_of_roots_with_overlapping_variables_in_a_big_transaction_all_commit(session):
    roots = [book_iri(400 + n) for n in range(12)]
    async with session.transaction() as t:
        for iri in roots:
            await t.add_graph(iri, title(iri, "new"))
    assert [await stored_title(session, i) for i in roots] == ["new"] * 12


# -- the diagnosis: gone, at another version, restored --------------------------------------------


async def test_a_replaced_root_removed_meanwhile_is_a_conflict(session, other, seeded):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await other.remove(A, seeded[A])
    assert refused.value.iris == (A,)
    assert "no longer at version" in str(refused.value)
    assert not await stored(session, A)


async def test_a_removed_root_removed_and_replaced_by_others_conflicts_with_a_second_change(
    session, other, seeded
):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(A, seeded[A])
            await t.replace_graph(B, title(B, "mine"), seeded[B])
            await other.remove(A, seeded[A])
    assert refused.value.iris == (A,)
    assert await stored_title(session, B) == "first"


async def test_an_added_root_added_by_another_session_meanwhile_conflicts(session, other, seeded):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.add_graph(C, title(C, "mine"))
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await other.add_graph(C, title(C, "theirs"))
    assert refused.value.iris == (C,)
    assert await stored_title(session, C) == "theirs"
    assert await stored_title(session, A) == "first"


async def test_the_conflict_iris_are_plain_strings_of_the_roots_not_graph_iris(
    session, other, seeded
):
    await other.replace_graph(A, title(A, "theirs"), seeded[A])
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
    assert refused.value.iris == (A,)
    assert graph_of(A) not in refused.value.iris


async def test_conflict_iris_are_equal_to_str_roots_when_the_caller_passed_urirefs(
    session, other, seeded
):
    await other.replace_graph(A, title(A, "theirs"), seeded[A])
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(URIRef(A), title(A, "mine"), seeded[A])
    # PD-7: iris is tuple[str, ...]; a URIRef never equals a str, so a caller comparing with a str fails
    assert refused.value.iris == (A,)
    assert all(type(i) is str for i in refused.value.iris)


# -- removes only ---------------------------------------------------------------------------------


async def test_removes_only_where_one_root_was_replaced_meanwhile_names_just_that_one(
    session, other, seeded
):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(A, seeded[A])
            await t.remove(B, seeded[B])
            await other.replace_graph(B, title(B, "theirs"), seeded[B])
    assert refused.value.iris == (B,)
    assert await stored(session, A), "the guard failed, so A stays too"
    assert await stored(session, B)


# -- loaded graphs --------------------------------------------------------------------------------


async def test_a_replace_keeping_its_loaded_graphs_and_an_add_with_a_new_one_in_one_transaction(
    store, session, seeded
):
    loaded_a = await session.load_graph(A, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    a2 = await session.replace_graph(A, title(A, "kept"), seeded[A], loaded_graphs=[loaded_a])
    loaded_c = await session.load_graph(C, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "second"), a2)  # loaded_graphs None: keep the registered
        await t.add_graph(C, title(C, "new"), loaded_graphs=[loaded_c])
    assert await has_triples(store, loaded_a)
    assert await has_triples(store, loaded_c)
    assert await session.loaded_graphs(A) == [loaded_a]
    assert await session.loaded_graphs(C) == [loaded_c]


async def test_a_replace_dropping_loaded_graphs_does_not_touch_the_other_roots_loaded_graph(
    store, session, seeded
):
    loaded_a = await session.load_graph(A, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    loaded_b = await session.load_graph(B, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    a2 = await session.replace_graph(A, title(A, "k"), seeded[A], loaded_graphs=[loaded_a])
    b2 = await session.replace_graph(B, title(B, "k"), seeded[B], loaded_graphs=[loaded_b])
    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "second"), a2, loaded_graphs=[])
        await t.replace_graph(B, title(B, "second"), b2)
    assert not await has_triples(store, loaded_a)
    assert await has_triples(store, loaded_b)
    assert await session.loaded_graphs(B) == [loaded_b]


async def test_removing_a_root_empties_its_loaded_graphs_and_leaves_the_others(
    store, session, seeded
):
    loaded_a = await session.load_graph(A, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    loaded_b = await session.load_graph(B, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    a2 = await session.replace_graph(A, title(A, "k"), seeded[A], loaded_graphs=[loaded_a])
    await session.replace_graph(B, title(B, "k"), seeded[B], loaded_graphs=[loaded_b])
    async with session.transaction() as t:
        await t.remove(A, a2)
        await t.add_graph(C, title(C, "new"))
    assert not await has_triples(store, loaded_a)
    assert await has_triples(store, loaded_b)
    assert not await ask(
        store, ENTRY, registry=term(DEFAULT_IRIS.registry(TENANT)), graph=term(loaded_a)
    )


async def test_a_loaded_graph_of_a_root_removed_in_the_same_transaction_cannot_be_claimed_by_another(
    store, session, seeded
):
    loaded_a = await session.load_graph(A, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    a2 = await session.replace_graph(A, title(A, "k"), seeded[A], loaded_graphs=[loaded_a])
    sent = len(store.sent("update"))
    with pytest.raises(InvalidIri):
        async with session.transaction() as t:
            await t.remove(A, a2)
            await t.replace_graph(B, title(B, "mine"), seeded[B], loaded_graphs=[loaded_a])
    assert len(store.sent("update")) == sent
    assert await has_triples(store, loaded_a)


# -- the marker -----------------------------------------------------------------------------------


async def test_two_transactions_of_one_session_use_two_markers(store, session, seeded):
    for n in (1, 2):
        async with session.transaction() as t:
            await t.add_graph(book_iri(500 + n), title(book_iri(500 + n), "new"))
    first, second = store.sent("update")[-2:]
    assert set(URN_MARKER.findall(first)).isdisjoint(URN_MARKER.findall(second))
    assert len(set(URN_MARKER.findall(first))) == 1, "one marker per transaction"


async def test_two_open_transactions_of_one_session_use_two_markers(store, session):
    async with session.transaction() as outer:
        await outer.add_graph(C, title(C, "outer"))
        async with session.transaction() as inner:
            await inner.add_graph(D, title(D, "inner"))
    first, second = store.sent("update")[-2:]
    assert set(URN_MARKER.findall(first)).isdisjoint(URN_MARKER.findall(second))
    assert await stored_title(session, C) == "outer"
    assert await stored_title(session, D) == "inner"


async def test_a_stray_marker_does_not_stop_a_later_transaction_and_is_left_alone(
    store, session, seeded
):
    registry = term(DEFAULT_IRIS.registry(TENANT))
    stray = URIRef("urn:uuid:00000000-0000-4000-8000-000000000000")
    await store.update(
        FAKE_DATABASE,
        fill(
            'INSERT DATA { GRAPH $registry { $stray a $marker ; $started "2020-01-01T00:00:00Z" } }',
            registry=registry,
            stray=term(stray),
            marker=term(v.COMMIT_MARKER),
            started=term(v.STARTED_AT),
        ),
    )
    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "second"), seeded[A])
        await t.add_graph(C, title(C, "new"))
    assert await stored_title(session, A) == "second"
    assert await ask(
        store,
        "ASK { GRAPH $registry { $m a $marker } }",
        registry=registry,
        m=term(stray),
        marker=term(v.COMMIT_MARKER),
    )


async def test_a_stray_marker_is_not_a_graph_owner_or_a_pending_load_for_the_sweep(
    store, session, seeded
):
    registry = DEFAULT_IRIS.registry(TENANT)
    stray = URIRef("urn:uuid:00000000-0000-4000-8000-000000000000")
    await store.update(
        FAKE_DATABASE,
        fill(
            'INSERT DATA { GRAPH $registry { $stray a $marker ; $started "2020-01-01T00:00:00Z" } }',
            registry=term(registry),
            stray=term(stray),
            marker=term(v.COMMIT_MARKER),
            started=term(v.STARTED_AT),
        ),
    )
    owned, loaded_at = await _registry_view(store, FAKE_DATABASE, registry)
    assert str(stray) not in owned and str(stray) not in loaded_at


async def test_a_stray_marker_does_not_make_a_failed_guard_pass(store, session, other, seeded):
    """The marked operations match the transaction's own marker only, not any marker."""
    registry = term(DEFAULT_IRIS.registry(TENANT))
    await store.update(
        FAKE_DATABASE,
        fill(
            "INSERT DATA { GRAPH $registry { $stray a $marker } }",
            registry=registry,
            stray=term(URIRef("urn:uuid:00000000-0000-4000-8000-000000000000")),
            marker=term(v.COMMIT_MARKER),
        ),
    )
    with pytest.raises(Conflict):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.add_graph(C, title(C, "mine"))
            await other.replace_graph(A, title(A, "theirs"), seeded[A])
    assert not await stored(session, C), "a stray marker must not let the operations run"
    assert await stored_title(session, A) == "theirs"


# -- failures while collecting ------------------------------------------------------------------


async def test_a_not_found_inside_the_block_propagates_and_sends_nothing(store, session, seeded):
    sent = len(store.sent("update"))
    with pytest.raises(NotFound):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.remove(C, "v")  # C was never stored
    assert len(store.sent("update")) == sent
    assert await stored_title(session, A) == "first"


async def test_a_not_found_caught_inside_the_block_leaves_the_others_to_commit(
    store, session, seeded
):
    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "mine"), seeded[A])
        with pytest.raises(NotFound):
            await t.replace_graph(C, title(C, "mine"), "v")
        await t.add_graph(D, title(D, "new"))
    assert await stored_title(session, A) == "mine"
    assert not await stored(session, C)
    assert await stored_title(session, D) == "new"


async def test_a_refused_change_caught_inside_the_block_does_not_claim_its_root(session, seeded):
    async with session.transaction() as t:
        with pytest.raises(InvalidIri):
            await t.add_graph("https://elsewhere.example/not-ours", title(C, "x"))
        with pytest.raises(NotFound):
            await t.remove(C, "v")
        await t.add_graph(C, title(C, "new"))
    assert await stored_title(session, C) == "new"


async def test_a_bad_loaded_graph_inside_the_block_sends_nothing(store, session, seeded):
    sent = len(store.sent("update"))
    with pytest.raises(InvalidIri):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.add_graph(C, title(C, "new"), loaded_graphs=[URIRef("https://example.org/x")])
    assert len(store.sent("update")) == sent


async def test_a_value_error_for_a_twice_claimed_root_caught_in_the_block_keeps_the_first_change(
    session, seeded
):
    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "first change"), seeded[A])
        with pytest.raises(ValueError):
            await t.replace_graph(A, title(A, "second change"), seeded[A])
    assert await stored_title(session, A) == "first change"


async def test_a_str_root_then_a_uriref_root_of_an_add_is_refused(session):
    with pytest.raises(ValueError):
        async with session.transaction() as t:
            await t.add_graph(C, title(C, "one"))
            await t.add_graph(URIRef(C), title(C, "two"))


# -- several transactions -------------------------------------------------------------------------


async def test_a_nested_transaction_that_commits_first_conflicts_the_outer_one(session, seeded):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as outer:
            await outer.replace_graph(A, title(A, "outer"), seeded[A])
            await outer.add_graph(C, title(C, "outer"))
            async with session.transaction() as inner:
                await inner.replace_graph(A, title(A, "inner"), seeded[A])
    assert refused.value.iris == (A,)
    assert await stored_title(session, A) == "inner"
    assert not await stored(session, C)


async def test_a_sequence_of_transactions_each_uses_the_token_the_last_returned(session, seeded):
    token = seeded[A]
    for n in range(5):
        async with session.transaction() as t:
            token = await t.replace_graph(A, title(A, f"v{n}"), token)
    assert (await session.get_graph(A))[2] == token
    assert await stored_title(session, A) == "v4"


# -- the tenant root ------------------------------------------------------------------------------


async def test_replacing_the_tenant_root_and_a_book_commit_together_and_conflict_together(
    store, session, other, seeded
):
    root_version = await session.add_graph(TENANT, title(TENANT, "Ghent"))
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(TENANT, title(TENANT, "Bruges"), root_version)
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await other.replace_graph(A, title(A, "theirs"), seeded[A])
    assert refused.value.iris == (A,)
    assert str((await session.get_graph(TENANT))[0].value(URIRef(TENANT), TITLE)) == "Ghent"
    async with session.transaction() as t:
        await t.replace_graph(TENANT, title(TENANT, "Bruges"), root_version)
        await t.replace_graph(B, title(B, "mine"), seeded[B])
    assert str((await session.get_graph(TENANT))[0].value(URIRef(TENANT), TITLE)) == "Bruges"


async def test_a_conflict_on_the_tenant_root_names_the_tenant_iri(session, other):
    root_version = await session.add_graph(TENANT, title(TENANT, "Ghent"))
    await other.replace_graph(TENANT, title(TENANT, "Theirs"), root_version)
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(TENANT, title(TENANT, "Mine"), root_version)
    assert refused.value.iris == (TENANT,)


# -- single-root methods keep their messages ------------------------------------------------------


async def test_single_root_conflict_messages_are_as_before(session, other, seeded):
    with pytest.raises(Conflict) as exists:
        await session.add_graph(A, title(A, "again"))
    assert str(exists.value) == f"{graph_of(A)} already exists"
    await other.replace_graph(A, title(A, "theirs"), seeded[A])
    with pytest.raises(Conflict) as stale:
        await session.replace_graph(A, title(A, "mine"), seeded[A])
    assert str(stale.value) == f"{graph_of(A)} is no longer at version {seeded[A]}"
    with pytest.raises(Conflict) as stale_remove:
        await session.remove(A, seeded[A])
    assert str(stale_remove.value) == f"{graph_of(A)} is no longer at version {seeded[A]}"


async def test_a_single_root_remove_of_a_missing_root_is_not_found_and_sends_nothing(
    store, session
):
    sent = len(store.sent("update"))
    with pytest.raises(NotFound):
        await session.remove(C, "v")
    assert len(store.sent("update")) == sent
