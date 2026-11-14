"""``Session.transaction``: several aggregate writes in one update request, all or nothing (atomic-commit 1.2).

A and B are stored books of the toy tenant, C and D new ones; "another session" is a second session on
the same fake store.
"""

import re
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

import pytest
from rdflib import RDF, Graph, Literal, URIRef

from rdf_persistence.domain.exceptions import Conflict, NotFound, StoreUnavailable
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import Condition
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.session import Session, remove_parts
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import TENANT, book_iri, graph_of

A, B, C, D = (book_iri(n) for n in (1, 2, 3, 4))
TITLE = URIRef("http://purl.org/dc/terms/title")
LOADED_TTL = '<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'
ENTRY = "ASK { GRAPH $registry { $graph ?p ?o } }"
ANY_MARKER = "ASK { GRAPH $registry { ?m a $marker } }"
HAS_TRIPLES = "ASK { GRAPH $g { ?s ?p ?o } }"


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


async def has_entry(store: FakeStore, iri: str) -> bool:
    return await ask(
        store,
        ENTRY,
        registry=term(DEFAULT_IRIS.registry(TENANT)),
        graph=term(URIRef(graph_of(iri))),
    )


async def a_marker_is_left(store: FakeStore) -> bool:
    return await ask(
        store,
        ANY_MARKER,
        registry=term(DEFAULT_IRIS.registry(TENANT)),
        marker=term(v.COMMIT_MARKER),
    )


async def test_tc01_replace_add_and_remove_commit_together(store, session, seeded):
    async with session.transaction() as t:
        a2 = await t.replace_graph(A, title(A, "second"), seeded[A])
        c1 = await t.add_graph(C, title(C, "new"))
        assert await t.remove(B, seeded[B]) is None
    assert (await session.get_graph(A))[2] == a2, "A holds the replace's token"
    assert (await session.get_graph(C))[2] == c1, "C holds the add's token"
    assert await stored_title(session, A) == "second", "A was replaced"
    assert not await stored(session, B), "B was removed"
    assert await has_entry(store, C), "the added root is registered"
    assert not await has_entry(store, B), "the removed root is unregistered"
    assert not await a_marker_is_left(store), "the marker was released"
    assert len(store.sent("update")) == 3, "two seeds and one request for the transaction"


async def test_tc02_a_replaced_root_changed_meanwhile_refuses_everything(
    store, session, other, seeded
):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.add_graph(C, title(C, "new"))
            await t.remove(B, seeded[B])
            await other.replace_graph(A, title(A, "theirs"), seeded[A])
    assert refused.value.iris == (A,)
    assert await stored_title(session, A) == "theirs"
    assert not await stored(session, C)
    assert await stored(session, B)
    assert not await a_marker_is_left(store)


async def test_tc03_adding_an_existing_root_refuses_the_whole_transaction(session, seeded):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.add_graph(B, title(B, "again"))
    assert refused.value.iris == (B,)
    assert (await session.get_graph(A))[2] == seeded[A]
    assert str(refused.value) == f"{B} already exists", "the root is named, not its graph"


async def test_tc04_removing_a_root_changed_meanwhile_conflicts(session, other, seeded):
    await other.replace_graph(B, title(B, "theirs"), seeded[B])
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(B, seeded[B])
    assert refused.value.iris == (B,)
    assert await stored(session, B)


async def test_tc05_a_second_change_on_one_root_raises_at_once_and_sends_nothing(
    store, session, seeded
):
    sent = len(store.sent("update"))
    with pytest.raises(ValueError, match="twice|already"):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.remove(A, seeded[A])
    assert len(store.sent("update")) == sent


async def test_tc06_an_exception_inside_the_block_sends_nothing(store, session, seeded):
    sent = len(store.sent("update"))
    with pytest.raises(RuntimeError, match="boom"):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            raise RuntimeError("boom")
    assert len(store.sent("update")) == sent
    assert await stored_title(session, A) == "first"


async def test_tc07_the_tenant_root_and_a_book_commit_together(store, session, seeded):
    async with session.transaction() as t:
        await t.add_graph(TENANT, title(TENANT, "Ghent"))
        await t.replace_graph(A, title(A, "second"), seeded[A])
    meta = DEFAULT_IRIS.meta(TENANT)
    assert await ask(store, HAS_TRIPLES, g=term(meta))
    assert not await ask(
        store, ENTRY, registry=term(DEFAULT_IRIS.registry(TENANT)), graph=term(meta)
    )
    assert await stored_title(session, A) == "second"


async def test_tc08_a_replace_with_no_loaded_graphs_empties_the_old_ones(store, session, seeded):
    loaded = await session.load_graph(A, LOADED_TTL.encode(), rdf_format=RdfFormat.TURTLE)
    a2 = await session.replace_graph(A, title(A, "mine"), seeded[A], loaded_graphs=[loaded])
    registry = term(DEFAULT_IRIS.registry(TENANT))
    assert await ask(store, ENTRY, registry=registry, graph=term(loaded)), (
        "the entry is there first"
    )
    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "second"), a2, loaded_graphs=[])
        await t.add_graph(C, title(C, "new"))
    assert not await ask(store, HAS_TRIPLES, g=term(loaded)), "the loaded graph is emptied"
    assert not await ask(store, ENTRY, registry=registry, graph=term(loaded)), "its entry is gone"
    assert await stored(session, C), "C is stored"


async def test_tc09_an_empty_transaction_sends_nothing(store, session):
    async with session.transaction():
        pass
    assert store.sent("update") == []


async def test_tc10_a_failing_store_update_leaves_the_store_unchanged(store, session, seeded):
    store.on("update", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.add_graph(C, title(C, "new"))
    assert await stored_title(session, A) == "first"
    assert not await stored(session, C)


async def test_tc11_of_two_transactions_on_one_version_the_second_conflicts(session, other, seeded):
    async with session.transaction() as first:
        await first.replace_graph(A, title(A, "one"), seeded[A])
    with pytest.raises(Conflict) as refused:
        async with other.transaction() as second:
            await second.replace_graph(A, title(A, "two"), seeded[A])
    assert refused.value.iris == (A,)
    assert await stored_title(session, A) == "one"


async def test_tc12_a_commit_that_applied_is_a_success_though_another_writer_changed_a_graph(
    store, session, other, seeded
):
    async def meanwhile() -> None:
        store.after_update = None
        _, _, a2 = await other.get_graph(A)
        await other.replace_graph(A, title(A, "theirs"), a2)

    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "mine"), seeded[A])
        b2 = await t.replace_graph(B, title(B, "mine"), seeded[B])
        store.after_update = meanwhile
    assert await stored_title(session, A) == "theirs"
    assert await stored_title(session, B) == "mine"
    assert (await session.get_graph(B))[2] == b2


async def test_tc12a_removes_only_are_never_a_success_after_a_failed_confirmation(
    session, other, seeded
):
    await other.replace_graph(B, title(B, "theirs"), seeded[B])
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(B, seeded[B])
    assert refused.value.iris == (B,)
    assert await stored(session, B)


async def test_removing_a_root_that_another_writer_removed_meanwhile_is_a_success(
    store, session, other, seeded
):
    """PD-17e: the guard fails, nothing is written, and the confirming ASK (the graph is empty) holds."""
    async with session.transaction() as t:
        await t.remove(B, seeded[B])
        await other.remove(B, seeded[B])
    assert not await stored(session, B), "B stays removed"
    assert await stored(session, A), "A is untouched"
    assert not await a_marker_is_left(store), "no marker is left"


async def test_a_removed_root_that_another_writer_removed_meanwhile_is_named_with_a_second_change(
    session, other, seeded
):
    """PD-17f: with a replace beside it the remove cannot count as done; its root is named."""
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(A, seeded[A])
            await t.replace_graph(B, title(B, "mine"), seeded[B])
            await other.remove(A, seeded[A])
    assert refused.value.iris == (A,), "the root whose graph is gone is named"
    assert str(refused.value) == f"{A} was removed by someone else since it was read", "says gone"
    assert await stored_title(session, B) == "first", "B was not replaced"


async def test_a_store_failure_during_the_confirming_ask_propagates_though_the_commit_applied(
    store, session, seeded
):
    async def fail_next_query() -> None:
        store.after_update = None
        store.on("query", StoreUnavailable("down"))

    with pytest.raises(StoreUnavailable):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            store.after_update = fail_next_query
    assert await stored_title(session, A) == "mine", "the commit applied; the caller re-reads"


async def test_tc13_a_str_and_a_uriref_of_one_root_are_one_claim(session, seeded):
    with pytest.raises(ValueError, match="twice|already"):
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])
            await t.remove(URIRef(A), seeded[A])


async def test_the_returned_graph_is_what_the_transaction_wrote(session, seeded):
    async with session.transaction() as t:
        await t.replace_graph(A, title(A, "second"), seeded[A])
    graph, _, _ = await session.get_graph(A)
    assert isinstance(graph, Graph)
    assert (URIRef(A), TITLE, Literal("second")) in graph


async def test_the_conflict_names_every_conflicting_root_sorted(session, other, seeded):
    await other.replace_graph(B, title(B, "theirs"), seeded[B])
    await other.replace_graph(A, title(A, "theirs"), seeded[A])
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(B, title(B, "mine"), seeded[B])
            await t.replace_graph(A, title(A, "mine"), seeded[A])
    assert refused.value.iris == tuple(sorted((A, B)))


async def test_a_lost_race_with_no_culprit_says_so_with_no_iris(store, session, seeded):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.replace_graph(A, title(A, "mine"), seeded[A])

            async def restore_old_state() -> None:
                # a writer put A back at the version the transaction guarded on, after the guard held
                store.after_update = None
                text = fill(
                    "DELETE { GRAPH $g { $g $p ?new } } INSERT { GRAPH $g { $g $p $old } } "
                    "WHERE { GRAPH $g { $g $p ?new } }",
                    g=term(URIRef(graph_of(A))),
                    p=term(v.VERSION),
                    old=term(Literal(seeded[A])),
                )
                await store.update(FAKE_DATABASE, text)

            store.after_update = restore_old_state
    assert refused.value.iris == ()
    assert str(refused.value) == "the commit lost a race with another writer; read again and retry"


# -- a transaction is single-use (PD-17c) ---------------------------------------------------------


async def test_a_transaction_used_after_its_block_committed_raises_instead_of_dropping_the_change(
    session, seeded
):
    async with session.transaction() as t:
        await t.add_graph(C, title(C, "new"))
    late = (
        lambda: t.add_graph(D, title(D, "late")),
        lambda: t.replace_graph(A, title(A, "late"), seeded[A]),
        lambda: t.remove(A, seeded[A]),
    )
    for use in late:
        with pytest.raises(RuntimeError, match="ended"):
            await use()
    assert not await stored(session, D)


async def test_a_transaction_used_after_its_block_raised_raises_too(session, seeded):
    with pytest.raises(KeyError):
        async with session.transaction() as t:
            raise KeyError("boom")
    with pytest.raises(RuntimeError, match="ended"):
        await t.add_graph(C, title(C, "late"))


# -- _require_match: a guard that the aggregate still meets a rule (collaboration PD-15) ------------

KIND = URIRef("https://example.org/Kind")


def kind(iri: str, text: str) -> list:
    return [(URIRef(iri), RDF.type, KIND), *title(iri, text)]


def titled(text: str) -> list[Condition]:
    return [Condition(predicate=str(TITLE), value=text)]


@pytest.fixture
async def typed(session) -> dict[str, str]:
    """A titled "first" and B titled "second", both of ``KIND``."""
    return {
        A: await session.add_graph(A, kind(A, "first")),
        B: await session.add_graph(B, kind(B, "second")),
    }


async def test_a_match_guard_that_holds_lets_the_commit_through(session, typed):
    async with session.transaction() as t:
        await t.remove(A, typed[A])
        t._require_match(A, str(KIND), titled("first"))
    assert not await stored(session, A)


async def test_a_match_guard_that_fails_refuses_the_commit_and_writes_nothing(
    store, session, typed
):
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            await t.remove(A, typed[A])
            t._require_match(A, str(KIND), titled("other"))
    assert refused.value.iris == (), "a guard that only stopped holding names no one"
    assert str(refused.value) == "the commit lost a race with another writer; read again and retry"
    assert await stored(session, A)
    assert not await a_marker_is_left(store)


async def test_the_class_of_a_match_guard_must_be_the_class_of_the_aggregate(session, typed):
    with pytest.raises(Conflict):
        async with session.transaction() as t:
            await t.remove(A, typed[A])
            t._require_match(A, "https://example.org/Other", titled("first"))
    assert await stored(session, A)


async def test_two_match_guards_of_one_transaction_do_not_join(session, typed):
    async with session.transaction() as t:
        await t.remove(A, typed[A])
        await t.remove(B, typed[B])
        t._require_match(A, str(KIND), titled("first"))
        t._require_match(B, str(KIND), titled("second"))
    assert not await stored(session, A) and not await stored(session, B)


async def test_a_match_guard_after_the_block_ended_raises(session, typed):
    async with session.transaction() as t:
        await t.remove(A, typed[A])
    with pytest.raises(RuntimeError, match="ended"):
        t._require_match(B, str(KIND), titled("second"))


# -- _require_present: a guard that the aggregate still exists (collaboration PD-15) ---------------


async def test_a_present_guard_that_holds_lets_the_commit_through(session, seeded):
    async with session.transaction() as t:
        t._require_present(A)
        await t.add_graph(C, title(C, "new"))
    assert await stored(session, C), "a is there, so the commit went through"


async def test_a_present_guard_on_a_removed_root_refuses_the_commit_and_names_it(
    store, session, other, seeded
):
    await other.remove(A, seeded[A])
    with pytest.raises(Conflict) as refused:
        async with session.transaction() as t:
            t._require_present(A)
            await t.add_graph(C, title(C, "new"))
    assert refused.value.iris == (A,), "the conflict names the root that is gone"
    said = str(refused.value)
    assert said == f"{A} was removed by someone else since it was read", "and says so in words"
    assert not await stored(session, C), "nothing was written"
    assert not await a_marker_is_left(store), "and no commit marker is left"


async def test_two_present_guards_of_one_transaction_do_not_join(session, seeded):
    async with session.transaction() as t:
        t._require_present(A)
        t._require_present(B)
        await t.add_graph(C, title(C, "new"))
    assert await stored(session, C), "both are there: two guards hold side by side"


async def test_a_present_guard_after_the_block_ended_raises(session, seeded):
    async with session.transaction() as t:
        await t.add_graph(C, title(C, "new"))
    with pytest.raises(RuntimeError, match="ended"):
        t._require_present(A)


# -- _DROP_DEPENDENTS: a remove also drops the records that point at the removed root --------------

NOTE = URIRef("https://example.org/Annot")
LINK = URIRef("https://example.org/about")
MENTIONS = URIRef("https://example.org/mentions")
PAIRS = ((NOTE, LINK),)


def annotation(iri: str, kind_of: URIRef, predicate: URIRef, target: str) -> list:
    return [(URIRef(iri), RDF.type, kind_of), (URIRef(iri), predicate, URIRef(target))]


@pytest.fixture
async def dropping(store) -> AsyncIterator[Session]:
    """A session that removes the dependents of ``PAIRS`` with their target."""
    async with fake_session(store, tenant_iri=TENANT, dependents=PAIRS) as s:
        yield s


async def test_a_remove_drops_the_graph_and_entry_of_each_dependent_and_nothing_else(
    store, dropping, seeded
):
    other_type = book_iri(11)  # another type, the same link
    other_link = book_iri(12)  # the type, another link: a reference, not a dependent
    other_target = book_iri(13)  # a dependent of B
    gone = [book_iri(14), book_iri(15)]
    for iri in gone:
        await dropping.add_graph(iri, annotation(iri, NOTE, LINK, A))
    await dropping.add_graph(other_type, annotation(other_type, KIND, LINK, A))
    await dropping.add_graph(other_link, annotation(other_link, NOTE, MENTIONS, A))
    await dropping.add_graph(other_target, annotation(other_target, NOTE, LINK, B))
    await dropping.remove(A, seeded[A])
    for iri in gone:
        assert not await stored(dropping, iri), f"{iri} is gone"
        assert not await has_entry(store, iri), f"{iri} has no registry entry"
    for iri in (B, other_type, other_link, other_target):
        assert await stored(dropping, iri), f"{iri} stays"
        assert await has_entry(store, iri), f"{iri} keeps its registry entry"
    assert not await stored(dropping, A), "the removed root itself is gone"


async def test_many_dependents_go_in_the_one_request_of_the_remove(store, dropping, seeded):
    for n in range(30, 40):
        await dropping.add_graph(book_iri(n), annotation(book_iri(n), NOTE, LINK, A))
    sent = len(store.sent("update"))
    await dropping.remove(A, seeded[A])
    assert len(store.sent("update")) == sent + 1, "one update request for the root and all ten"
    left = [n for n in range(30, 40) if await stored(dropping, book_iri(n))]
    assert left == [], "no dependent is left"


async def test_a_remove_without_pairs_is_the_request_it_always_was(store, session, seeded):
    await session.add_graph(C, annotation(C, NOTE, LINK, A))
    await session.remove(A, seeded[A])
    text = store.sent("update")[-1]
    match = re.search(r"urn:uuid:[0-9a-f-]+", text)
    assert match, "the request names its marker"
    removal = remove_parts(
        URIRef(graph_of(A)),
        DEFAULT_IRIS.registry(TENANT),
        URIRef(A),
        URIRef(match.group()),
        seeded[A],
    )[1]
    assert len(text.split(";\n")) == 2 + len(removal.split(";\n")), "start, the removal, release"
    assert removal in text, "the removal is the text remove_parts gives without pairs"
    assert "?d " not in text, "no dependents operation"
    assert await stored(session, C), "the would-be dependent stays"
