"""Collaboration against a real Fuseki: the reverse references of a resource (IT-01, IT-02) and
reference collections (IT-03, IT-04, IT-05)."""

import time
import uuid
from collections.abc import AsyncIterator, Callable

import pytest

from rdf_persistence import Action, CallerAccess, VerifiedCaller, generated_models
from rdf_persistence.domain.exceptions import Forbidden
from rdf_persistence.domain.generated.rp_collections import MembershipRule, SlotEquality
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.service.rp_service import ReferrerList
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session, open_session
from rdf_persistence.services.write_guards import WriteGuards
from tests.fixtures.library.generated.books import Book, Genre
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    ban,
    book_iri,
    caller,
    direct,
    dune,
    graph_of,
    held,
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)

B1, B2, B3, B5 = (book_iri(n) for n in (1, 2, 3, 5))
S1, S2 = shelf_iri(1), shelf_iri(2)
A, B = shelf_iri(3), shelf_iri(4)


@pytest.fixture
async def database(store) -> AsyncIterator[str]:
    """A fresh dataset for the test, dropped after it."""
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture
async def session(store, database) -> AsyncIterator[Session]:
    listings = Listings(load_schema(TOY_SCHEMA))
    guards = WriteGuards(toy_mapper(), generated_models(*MODULES), listings)
    async with open_session(
        store,
        database=database,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        listings=listings,
        guards=guards,
    ) as opened:
        yield opened


@pytest.fixture
def collaboration(session: Session) -> Callable[[VerifiedCaller, CallerAccess], Collaboration]:
    """Builds a ``Collaboration`` over the Fuseki session for a caller and its access."""
    view = load_schema(TOY_SCHEMA)
    rules = AccessRules(load_role_definitions(ROLES))

    def build(who: VerifiedCaller, access: CallerAccess) -> Collaboration:
        return Collaboration(
            session,
            view=view,
            rules=rules,
            iris=DEFAULT_IRIS,
            mapper=toy_mapper(),
            models=generated_models(*MODULES),
            listings=Listings(view),
            caller=who,
            access=access,
        )

    return build


async def put_book(session: Session, iri: str, **slots: str) -> Book:
    book = dune(iri, chapters=1, **slots)
    await session.add_graph(iri, toy_mapper().to_triples(book))
    return book


def refs(found: ReferrerList) -> list[tuple[str, str, str]]:
    return [(r.referrer, r.referrer_class, r.referrer_slot) for r in found.referrers or []]


async def test_a_resource_lists_the_aggregates_that_point_at_it(session, collaboration):
    await put_book(session, B1, shelf=S1)
    await put_book(session, B2, shelf=S1)
    await put_book(session, B3, shelf=S2)
    found = await collaboration(caller(principal=ADA), held(role("librarian"))).referrers(S1)
    assert refs(found) == [(B1, "Book", "shelf"), (B2, "Book", "shelf")], "b3 is on s2"
    assert found.hidden_count == 0, "ada may read both"


async def test_a_referrer_the_caller_may_not_read_is_counted_and_not_named(session, collaboration):
    await put_book(session, B1, shelf=S1)
    await put_book(session, B2, shelf=S1)
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(B2), BOB)])
    found = await collaboration(caller(principal=BOB), access).referrers(S1)
    assert refs(found) == [(B1, "Book", "shelf")], "bob may read only b1"
    assert found.hidden_count == 1, "b2 is counted"
    assert B2 not in found.model_dump_json(), "and never named"


async def test_a_slot_narrows_the_referrers(session, collaboration):
    await put_book(session, B1)
    await put_book(session, B3, sequel_of=B1)
    b2 = dune(B2, chapters=1)
    b2.chapters[0].notes[0].about = B1
    await session.add_graph(B2, toy_mapper().to_triples(b2))
    found = await collaboration(caller(principal=ADA), held(role("librarian"))).referrers(
        B1, slot="sequel_of"
    )
    assert refs(found) == [(B3, "Book", "sequel_of")], "the note's about is left out"


async def test_narrowing_does_not_change_the_hidden_count(session, collaboration):
    await put_book(session, B1, shelf=S1)
    await put_book(session, B2, shelf=S1)
    access = held(role("reader", who=BOB), bans=[ban(Action.READ, graph_of(B2), BOB)])
    found = await collaboration(caller(principal=BOB), access).referrers(S1, slot="sequel_of")
    assert refs(found) == [], "no readable referrer holds s1 by that slot"
    assert found.hidden_count == 1, "b2 is still counted, so the slot it uses stays unknown"


def poetry() -> MembershipRule:
    return MembershipRule(
        rule_equalities=[SlotEquality(equals_slot="genre", equals_value="poetry")]
    )


def fiction() -> MembershipRule:
    return MembershipRule(
        rule_equalities=[SlotEquality(equals_slot="genre", equals_value="fiction")]
    )


def a_shelf(iri: str, **slots):
    return shelf(iri).model_copy(update=slots)


async def put(session: Session, model) -> str:
    return await session.add_graph(model.id, toy_mapper().to_triples(model))


async def put_genre_book(session: Session, iri: str, genre: Genre = Genre.FICTION) -> None:
    await put(session, dune(iri, chapters=1).model_copy(update={"genre": genre.value}))


async def version_of(session: Session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


async def stored(session: Session, iri: str) -> bool:
    return bool(await session.heads([iri]))


def as_ada(collaboration):
    return collaboration(caller(principal=ADA), held(role("librarian")))


async def test_a_shelf_of_stored_books_is_saved_and_the_books_are_untouched(session):  # TC-15
    await put_genre_book(session, B1)
    await put_genre_book(session, B2)
    before = [await version_of(session, i) for i in (B1, B2)]
    work = UnitOfWork(session, toy_mapper())
    work.add(a_shelf(S1, had_member=[B1, B2]))
    await work.commit()
    assert await stored(session, S1), "the shelf is stored"
    assert before == [await version_of(session, i) for i in (B1, B2)], "the books are untouched"


async def test_a_rule_shelf_gains_a_newly_saved_poetry_book(session, collaboration):  # TC-23
    await put(session, a_shelf(S1, membership_rule=poetry()))
    await put_genre_book(session, B5, Genre.POETRY)
    await put_genre_book(session, B1)
    found = await as_ada(collaboration).members(S1)
    assert found.member_iris == [B5], "the poetry book, not the fiction one"


async def test_nested_shelves_are_read_deeply(session, collaboration):  # TC-26
    await put_genre_book(session, B1)
    await put(session, a_shelf(B, member_class="Book", had_member=[B1]))
    await put(session, a_shelf(A, member_class="Shelf", had_member=[B]))
    build = as_ada(collaboration)
    assert (await build.members(A)).member_iris == [B], "not deep: only the shelf"
    assert (await build.members(A, deep=True)).member_iris == sorted([B, B1]), "deep: and its book"


async def test_a_deep_read_of_shelves_that_hold_each_other_ends(session, collaboration):  # TC-27
    await put(session, a_shelf(A, member_class="Shelf"))
    await put(session, a_shelf(B, member_class="Shelf", had_member=[A]))
    await session.replace_graph(
        A,
        toy_mapper().to_triples(a_shelf(A, member_class="Shelf", had_member=[B])),
        await version_of(session, A),
    )
    found = await as_ada(collaboration).members(A, deep=True)
    assert found.member_iris == sorted([A, B]), "each is the other's member, and the read ends"


async def test_a_cascade_deletes_the_shelf_and_its_members_in_one_request(
    store, session, collaboration, monkeypatch
):  # TC-34
    await put_genre_book(session, B1)
    await put_genre_book(session, B2)
    await put_genre_book(session, B3, Genre.POETRY)
    await put(session, a_shelf(S1, had_member=[B1], membership_rule=poetry()))
    sent: list[str] = []
    original = store.update

    async def counting(dataset: str, text: str) -> None:
        sent.append(text)
        await original(dataset, text)

    monkeypatch.setattr(store, "update", counting)
    await as_ada(collaboration).delete_cascade(S1, await version_of(session, S1))
    assert len(sent) == 1, "one update request"
    assert not any([await stored(session, i) for i in (S1, B1, B3)]), "s1, b1 and b3 are gone"
    assert await stored(session, B2), "a fiction book that nothing names stays"


async def test_a_member_the_caller_may_not_delete_refuses_the_cascade(session, collaboration):
    await put_genre_book(session, B1)
    await put_genre_book(session, B2)
    await put(session, a_shelf(S1, had_member=[B1, B2]))
    access = held(
        role("reader"), direct(Action.DELETE, graph_of(S1)), direct(Action.DELETE, graph_of(B1))
    )
    with pytest.raises(Forbidden) as refused:
        await collaboration(caller(), access).delete_cascade(S1, await version_of(session, S1))
    assert B2 in str(refused.value) and B1 not in str(refused.value), "names b2 only"  # TC-35
    assert await stored(session, S1) and await stored(session, B1), "nothing is deleted"


async def test_the_collections_of_a_book_among_fifty_rule_shelves(session, collaboration):  # IT-05
    await put_genre_book(session, B3, Genre.POETRY)
    shelves = [shelf_iri(100 + n) for n in range(50)]
    for n, iri in enumerate(shelves):
        await put(session, a_shelf(iri, membership_rule=poetry() if n % 3 == 0 else fiction()))
    build = as_ada(collaboration)
    started = time.perf_counter()
    found = await build.collections_of(B3)
    elapsed = time.perf_counter() - started
    print(f"IT-05 collections_of over 50 rule shelves: {elapsed:.3f} s")
    assert found.member_iris == shelves[::3], "exactly the shelves whose rule b3 meets"
