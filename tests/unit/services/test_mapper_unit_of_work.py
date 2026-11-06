"""The object-level unit of work over a session (PD-7a): get, add, commit, with the fake store."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from rdflib import URIRef

from rdf_persistence.domain.exceptions import Conflict, NotFound
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import registry_graph_iri
from rdf_persistence.services.mapper import UnitOfWork, new_part
from rdf_persistence.services.session import Session
from rdf_persistence.testkit.fakes import FAKE_DATABASE, FakeStore, fake_session
from tests.fixtures.library.generated.books import Book, Chapter
from tests.fixtures.library.generated.library import Library
from tests.toy import ADA, TENANT, access, book_iri, dune, toy_mapper

BEN = "https://example.org/people/ben"
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
TTL = b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


def session_of(store: FakeStore, who: str = ADA):
    return fake_session(store, tenant_iri=TENANT, principal=Principal(id=who), clock=lambda: NOW)


@pytest.fixture
async def session(store: FakeStore) -> AsyncIterator[Session]:
    async with session_of(store) as opened:
        yield opened


def unit(session: Session) -> UnitOfWork:
    return UnitOfWork(session, toy_mapper())


def part_ids(book: Book) -> list[str]:
    chapters = book.chapters or []
    return [c.id for c in chapters] + [n.id for c in chapters for n in c.notes or []]


async def test_a_new_book_with_parts_lacking_ids_is_stored_with_minted_part_iris(session):
    iri = book_iri(1)
    book = dune(iri)
    work = unit(session)
    work.add(book)
    await work.commit()
    stored = await unit(session).get(Book, iri)
    assert sorted(part_ids(stored)) == sorted(part_ids(book)), "the minted IRIs are the ones stored"
    assert all(i.startswith(f"{iri}/parts/") for i in part_ids(stored)), "under the root"


async def test_a_re_read_and_re_commit_keeps_the_part_iris(session):
    iri = book_iri(2)
    first = unit(session)
    first.add(dune(iri))
    await first.commit()
    second = unit(session)
    book = await second.get(Book, iri)
    before = part_ids(book)
    book.label = "Dune, revised"
    second.add(book)
    await second.commit()
    after = await unit(session).get(Book, iri)
    assert sorted(part_ids(after)) == sorted(before), "the parts keep their IRIs"
    assert after.label == "Dune, revised", "the change is stored"


async def test_a_change_is_tracked_as_a_later_commit_by_its_author(store):
    iri = book_iri(3)
    async with session_of(store, ADA) as ada:
        work = unit(ada)
        work.add(dune(iri))
        await work.commit()
    async with session_of(store, BEN) as ben:
        work = unit(ben)
        book = await work.get(Book, iri)
        book.isbn = "9780441172719"
        work.add(book)
        await work.commit()
        read = await unit(ben).get(Book, iri)
    assert (read.creator, read.contributor) == (ADA, [BEN]), "tracking is read back"
    assert read.created == NOW and read.modified == NOW, "the commit times are read back"


async def test_grants_are_stored_as_skolemised_parts_and_read_back(session):
    record = access(grants=[Grant(assignee=ADA, target=TENANT, role="librarian")])
    work = unit(session)
    work.add(record)
    await work.commit()
    again = unit(session)
    first = await again.get(type(record), record.id)
    assert first.grants == record.grants, "grants nest back as objects"
    again.add(first)
    await again.commit()
    assert (await unit(session).get(type(record), record.id)).grants == record.grants


async def test_the_tenant_root_is_stored_in_the_meta_graph(session):
    library = Library(id=TENANT, label="City library", description="d", city="Brussels")
    work = unit(session)
    work.add(library)
    await work.commit()
    back = await unit(session).get(Library, TENANT)
    assert (back.city, back.creator) == ("Brussels", ADA)


async def test_two_editors_of_one_book_the_second_commit_conflicts(session):
    iri = book_iri(4)
    seed = unit(session)
    seed.add(dune(iri))
    await seed.commit()
    one, two = unit(session), unit(session)
    first, second = await one.get(Book, iri), await two.get(Book, iri)
    first.label, second.label = "one", "two"
    one.add(first)
    await one.commit()
    two.add(second)
    with pytest.raises(Conflict):
        await two.commit()
    assert (await unit(session).get(Book, iri)).label == "one", "the first edit stands"


async def test_a_new_book_over_an_existing_one_conflicts(session):
    seed = unit(session)
    seed.add(dune(book_iri(5)))
    await seed.commit()
    again = unit(session)
    again.add(dune(book_iri(5)))
    with pytest.raises(Conflict):
        await again.commit()


async def test_a_book_read_twice_is_the_same_object(session):
    seed = unit(session)
    seed.add(dune(book_iri(6)))
    await seed.commit()
    work = unit(session)
    assert await work.get(Book, book_iri(6)) is await work.get(Book, book_iri(6))


async def test_a_commit_writes_only_what_was_added_and_only_once(session, store):
    iri = book_iri(7)
    work = unit(session)
    work.add(dune(iri))
    await work.commit()
    writes = len(store.sent("update"))
    await work.get(Book, iri)
    await work.commit()
    assert len(store.sent("update")) == writes, "nothing changed, nothing is written"


async def test_a_committed_book_can_be_changed_and_committed_again_by_the_same_unit(session):
    iri = book_iri(8)
    work = unit(session)
    book = dune(iri)
    work.add(book)
    await work.commit()
    book.label = "Dune II"
    work.add(book)
    await work.commit()
    assert (await unit(session).get(Book, iri)).label == "Dune II"


async def test_a_missing_book_is_not_found(session):
    with pytest.raises(NotFound):
        await unit(session).get(Book, book_iri(9))


async def test_only_roots_are_added(session):
    with pytest.raises(ValueError, match="not an aggregate root"):
        unit(session).add(new_part(Chapter, book_iri(10), number=1))


async def test_a_chapter_added_to_a_read_book_gets_a_part_iri_that_is_kept(session):
    iri = book_iri(11)
    seed = unit(session)
    seed.add(dune(iri, chapters=1))
    await seed.commit()
    work = unit(session)
    book = await work.get(Book, iri)
    book.chapters = [*book.chapters, new_part(Chapter, iri, number=2)]
    work.add(book)
    await work.commit()
    stored = await unit(session).get(Book, iri)
    assert sorted(part_ids(stored)) == sorted(part_ids(book))
    assert URIRef(stored.chapters[1].id).startswith(f"{iri}/parts/")


async def test_getting_a_root_as_the_wrong_class_is_a_type_error(session):
    seed = unit(session)
    seed.add(dune(book_iri(12)))
    await seed.commit()
    work = unit(session)
    await work.get(Book, book_iri(12))
    with pytest.raises(TypeError, match="Book"):
        await work.get(Chapter, book_iri(12))


async def test_editing_a_book_through_the_unit_of_work_keeps_its_loaded_graphs(store, session):
    iri = book_iri(13)
    loaded = await session.load_graph(iri, TTL, rdf_format=RdfFormat.TURTLE)
    await session.add_graph(iri, list(toy_mapper().to_graph(dune(iri))), [loaded])
    work = unit(session)
    book = await work.get(Book, iri)
    book.label = "Renamed"
    work.add(book)
    await work.commit()
    kept = f"ASK {{ GRAPH <{loaded}> {{ ?s ?p ?o }} }}"
    entry = f"ASK {{ GRAPH <{registry_graph_iri(TENANT)}> {{ <{loaded}> ?p ?o }} }}"
    assert (await store.query(FAKE_DATABASE, kept)).askAnswer, "the loaded graph keeps its triples"
    assert (await store.query(FAKE_DATABASE, entry)).askAnswer, "and its registry entry"
