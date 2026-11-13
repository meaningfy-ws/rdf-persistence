"""The object-level unit of work over a session (PD-7a): get, add, commit, with the fake store."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from rdflib import URIRef

from rdf_persistence.domain.exceptions import BadQuery, CommitTooLarge, Conflict, NotFound
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
)
from rdf_persistence.services.mapper import UnitOfWork, new_part
from rdf_persistence.services.session import Session
from rdf_persistence.testkit.fakes import FAKE_DATABASE, FakeStore, fake_session
from tests.fixtures.library.generated.books import Book, Chapter
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
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
    assert read.created == NOW, "the creation time is read back"
    assert read.modified == NOW, "the modification time is read back"


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
    assert writes == 1, "one update request per commit"
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
    entry = f"ASK {{ GRAPH <{DEFAULT_IRIS.registry(TENANT)}> {{ <{loaded}> ?p ?o }} }}"
    assert (await store.query(FAKE_DATABASE, kept)).askAnswer, "the loaded graph keeps its triples"
    assert (await store.query(FAKE_DATABASE, entry)).askAnswer, "and its registry entry"


async def seed(session, *numbers: int) -> None:
    work = unit(session)
    for number in numbers:
        work.add(dune(book_iri(number)))
    await work.commit()


async def change_elsewhere(store, iri: str, label: str) -> None:
    async with session_of(store, BEN) as other:
        work = unit(other)
        book = await work.get(Book, iri)
        book.label = label
        work.add(book)
        await work.commit()


async def test_a_conflict_on_one_book_leaves_every_book_of_the_commit_unwritten(session, store):
    a, b = book_iri(20), book_iri(21)
    await seed(session, 20, 21)
    work = unit(session)
    first, second = await work.get(Book, a), await work.get(Book, b)
    await change_elsewhere(store, b, "elsewhere")
    first.label = "mine"
    work.add(first)
    work.add(second)
    with pytest.raises(Conflict) as raised:
        await work.commit()
    assert raised.value.iris == (b,), "only the changed book is named"
    assert (await unit(session).get(Book, a)).label == dune(a).label, "A is unchanged in the store"
    assert (await unit(session).get(Book, b)).label == "elsewhere", "B keeps the other edit"


async def test_one_commit_stores_new_books_and_removes_a_read_one_in_one_request(session, store):
    a = book_iri(22)
    await seed(session, 22)
    work = unit(session)
    gone = await work.get(Book, a)
    news = [dune(book_iri(n)) for n in (23, 24, 25)]
    for book in news:
        work.add(book)
    work.remove(gone)
    before = len(store.sent("update"))
    await work.commit()
    assert len(store.sent("update")) == before + 1, "one update request"
    for book in news:
        assert (await unit(session).get(Book, book.id)).label == book.label, "stored as added"
        assert work.version(book.id) == (await session.get_graph(book.id))[2], "with its new token"
    with pytest.raises(NotFound):
        await unit(session).get(Book, a)
    with pytest.raises(LookupError):
        work.version(a)


async def test_version_of_a_read_book_is_the_session_token(session):
    iri = book_iri(26)
    await seed(session, 26)
    work = unit(session)
    await work.get(Book, iri)
    assert work.version(iri) == (await session.get_graph(iri))[2]


async def test_version_after_a_commit_is_the_new_token(session):
    iri = book_iri(27)
    await seed(session, 27)
    work = unit(session)
    book = await work.get(Book, iri)
    read_at = work.version(iri)
    book.label = "changed"
    work.add(book)
    await work.commit()
    assert work.version(iri) != read_at
    assert work.version(iri) == (await session.get_graph(iri))[2]


async def test_version_of_an_unread_book_is_a_lookup_error_naming_it(session):
    with pytest.raises(LookupError) as raised:
        unit(session).version(book_iri(28))
    assert raised.value.args == (book_iri(28),), "the error names the IRI"


async def test_a_book_not_read_here_cannot_be_removed(session):
    with pytest.raises(ValueError, match="read"):
        unit(session).remove(dune(book_iri(29)))


async def test_a_conflict_in_a_commit_with_a_removal_keeps_the_removed_book(session, store):
    a, b = book_iri(30), book_iri(31)
    await seed(session, 30, 31)
    work = unit(session)
    first, second = await work.get(Book, a), await work.get(Book, b)
    first.label = "mine"
    work.add(first)
    work.remove(second)
    await change_elsewhere(store, a, "elsewhere")
    with pytest.raises(Conflict) as raised:
        await work.commit()
    assert raised.value.iris == (a,)
    assert (await unit(session).get(Book, b)).id == b, "B is still stored"


async def test_a_failed_commit_leaves_the_held_book_and_its_version_unchanged(session, store):
    a, b = book_iri(32), book_iri(33)
    await seed(session, 32, 33)
    work = unit(session)
    first, second = await work.get(Book, a), await work.get(Book, b)
    read_at = work.version(a)
    await change_elsewhere(store, b, "elsewhere")
    first.label = "mine"
    work.add(first)
    work.add(second)
    with pytest.raises(Conflict):
        await work.commit()
    assert await work.get(Book, a) is first, "the held object is the one read"
    assert first.label == "mine", "with the edit it carried"
    assert work.version(a) == read_at, "and the version it was read at"


async def test_a_book_read_with_a_uriref_is_removed_and_refused_again_as_for_a_str(session):
    iri = book_iri(36)
    await seed(session, 36)
    work = unit(session)
    book = await work.get(Book, URIRef(iri))
    assert work.version(iri) == work.version(URIRef(iri)), "the version is found by either type"
    assert await work.get(Book, iri) is book, "a str reads the object a URIRef read"
    work.remove(book)
    await work.commit()
    with pytest.raises(NotFound):
        await unit(session).get(Book, iri)
    with pytest.raises(ValueError, match="removed"):
        work.add(book)


async def test_a_book_read_with_a_uriref_and_changed_is_replaced_not_added(session):
    iri = book_iri(37)
    await seed(session, 37)
    work = unit(session)
    book = await work.get(Book, URIRef(iri))
    book.label = "changed"
    work.add(book)
    await work.commit()
    assert (await unit(session).get(Book, iri)).label == "changed", "the stored book was replaced"


async def test_a_new_book_that_is_removed_before_commit_is_refused_at_remove(session):
    work = unit(session)
    book = dune(book_iri(34))
    work.add(book)
    with pytest.raises(ValueError, match="read"):
        work.remove(book)


async def test_remove_wins_over_an_earlier_add_and_a_later_add_is_refused(session):
    iri = book_iri(35)
    await seed(session, 35)
    work = unit(session)
    book = await work.get(Book, iri)
    work.add(book)
    work.remove(book)
    await work.commit()
    with pytest.raises(NotFound):
        await unit(session).get(Book, iri)
    with pytest.raises(ValueError, match="removed"):
        work.add(book)


# -- the size limit and the batch mode (atomic-commit 2.1: PD-8, PD-9) -------------------------


def limited(session: Session, max_roots: int) -> UnitOfWork:
    return UnitOfWork(session, toy_mapper(), max_roots=max_roots)


def steady_dune(iri: str) -> Book:
    """A book whose chapter has an IRI derived from the book, so a re-run builds the same one."""
    book = dune(iri, chapters=0)
    return book.model_copy(update={"chapters": [Chapter(id=f"{iri}/parts/chapter-1", number=1)]})


def three_books(first: int) -> list[Book]:
    return [steady_dune(book_iri(n)) for n in range(first, first + 3)]


def three_records(first: int) -> list[LibraryAccess]:
    """Roots that own anonymous parts (grants have no id): blank nodes, skolemised when stored."""
    return [
        access(grants=[Grant(assignee=ADA, target=TENANT, role="librarian")]).model_copy(
            update={"id": book_iri(n)}
        )
        for n in range(first, first + 3)
    ]


async def test_tc30_a_commit_over_the_limit_is_refused_naming_both_numbers_and_sends_nothing(
    session, store
):
    work = limited(session, 2)
    for book in three_books(40):
        work.add(book)
    sent = {kind: len(store.sent(kind)) for kind in ("query", "update")}
    with pytest.raises(CommitTooLarge, match=r"(?s)(?=.*\b3\b)(?=.*\b2\b)"):
        await work.commit()
    assert {kind: len(store.sent(kind)) for kind in ("query", "update")} == sent, "nothing sent"


async def test_tc30_removed_roots_count_towards_the_limit(session):
    await seed(session, 43)
    work = limited(session, 2)
    work.remove(await work.get(Book, book_iri(43)))
    work.add(dune(book_iri(44)))
    work.add(dune(book_iri(45)))
    with pytest.raises(CommitTooLarge):
        await work.commit()


async def test_tc31_batches_commit_one_transaction_per_max_roots(session, store):
    books = three_books(46)
    work = limited(session, 2)
    for book in books:
        work.add(book)
    before = len(store.sent("update"))
    await work.commit(batches=True)
    assert len(store.sent("update")) == before + 2, "two update requests"
    for book in books:
        stored_label = (await unit(session).get(Book, book.id)).label
        assert stored_label == book.label, "each book is stored with its label"
        stored_version = (await session.get_graph(book.id))[2]
        assert work.version(book.id) == stored_version, "the unit of work holds the stored token"


async def test_tc32_a_re_run_after_a_failed_batch_stores_each_book_once(session, store):
    first_run = limited(session, 2)
    for book in three_books(50):
        first_run.add(book)
    store.on("update", BadQuery("the store went away"), after=1)  # the second batch fails
    with pytest.raises(BadQuery, match="the store went away"):
        await first_run.commit(batches=True)
    kept = {n: first_run.version(book_iri(n)) for n in (50, 51)}
    sent = len(store.sent("update"))
    second_run = limited(session, 2)
    for book in three_books(50):
        second_run.add(book)
    await second_run.commit(batches=True)
    assert len(store.sent("update")) == sent + 1, "only the third book needed a request"
    for n in (50, 51):
        assert (await session.get_graph(book_iri(n)))[2] == kept[n], "the first versions stand"
        assert second_run.version(book_iri(n)) == kept[n], "taken as committed"
    third = (await unit(session).get(Book, book_iri(52))).label
    assert third == "Dune", "the third book is stored by the re-run"


async def test_tc32a_a_re_run_of_roots_with_anonymous_parts_is_idempotent(session, store):
    first_run = limited(session, 2)
    for record in three_records(60):
        first_run.add(record)
    store.on("update", BadQuery("the store went away"), after=1)
    with pytest.raises(BadQuery):
        await first_run.commit(batches=True)
    kept = {n: first_run.version(book_iri(n)) for n in (60, 61)}
    second_run = limited(session, 2)
    for record in three_records(60):
        second_run.add(record)  # new objects, so new blank nodes
    await second_run.commit(batches=True)
    for n in (60, 61):
        assert (await session.get_graph(book_iri(n)))[2] == kept[n], "not written twice"
    stored = await unit(session).get(LibraryAccess, book_iri(62))
    assert len(stored.grants) == 1, "the third was stored once"


async def test_tc32b_the_same_unit_of_work_retries_only_what_is_left(session, store):
    work = limited(session, 2)
    for book in three_books(70):
        work.add(book)
    store.on("update", BadQuery("the store went away"), after=1)
    with pytest.raises(BadQuery, match=r"batches committed"):
        await work.commit(batches=True)
    sent = len(store.sent("update"))
    await work.commit(batches=True)
    assert len(store.sent("update")) == sent + 1, "one request, for the third book"
    for n in (70, 71, 72):
        assert (await unit(session).get(Book, book_iri(n))).id == book_iri(n), f"book {n} stored"


async def test_a_re_run_of_books_with_random_part_iris_conflicts_and_duplicates_nothing(session):
    first_run = limited(session, 2)
    first_run.add(dune(book_iri(75)))  # new_part: random part IRIs
    await first_run.commit(batches=True)
    kept = first_run.version(book_iri(75))
    second_run = limited(session, 2)
    second_run.add(dune(book_iri(75)))
    with pytest.raises(Conflict) as raised:
        await second_run.commit(batches=True)
    assert raised.value.iris == (book_iri(75),), "the conflict names the re-added book"
    assert (await session.get_graph(book_iri(75)))[2] == kept, "the stored book is untouched"


async def test_tc33_a_batch_that_conflicts_stops_there_and_says_how_many_committed(session):
    clash = book_iri(82)
    seed_one = unit(session)
    seed_one.add(steady_dune(clash).model_copy(update={"label": "Another title"}))
    await seed_one.commit()
    work = limited(session, 2)
    for iri in (80, 81, 82):
        work.add(steady_dune(book_iri(iri)))  # only the title of the last differs from the stored
    with pytest.raises(Conflict, match=r"1 of 2 batches committed") as raised:
        await work.commit(batches=True)
    assert raised.value.iris == (clash,), "the same fields as the batch raised"
    assert (await unit(session).get(Book, book_iri(80))).id == book_iri(80), "batch one stands"
    assert (await unit(session).get(Book, clash)).label == "Another title", "the clash is kept"


async def test_tc34_a_commit_of_exactly_the_limit_is_one_request(session, store):
    work = limited(session, 2)
    books = three_books(90)[:2]
    for book in books:
        work.add(book)
    before = len(store.sent("update"))
    await work.commit()
    assert len(store.sent("update")) == before + 1, "one request"
    for book in books:
        stored_id = (await unit(session).get(Book, book.id)).id
        assert stored_id == book.id, "both books are stored"


# -- fixes after the stage 2 review (PD-20) ----------------------------------------------------


async def test_a_retry_after_a_failed_batch_does_not_rewrite_a_root_taken_as_committed(
    session, store
):
    """PD-20b: the equal root is taken in the batch that conflicts; the retry leaves it alone."""
    equal, clash = book_iri(95), book_iri(96)
    seeding = unit(session)
    seeding.add(steady_dune(equal))
    await seeding.commit()
    stored_version = seeding.version(equal)
    theirs = unit(session)
    theirs.add(steady_dune(clash).model_copy(update={"label": "Theirs"}))
    await theirs.commit()
    work = limited(session, 2)
    work.add(steady_dune(equal))
    work.add(steady_dune(clash))
    with pytest.raises(Conflict):
        await work.commit(batches=True)
    cleared = unit(session)
    cleared.remove(await cleared.get(Book, clash))
    await cleared.commit()
    sent = len(store.sent("update"))
    await work.commit(batches=True)
    assert len(store.sent("update")) == sent + 1, "one request, for the root that was refused"
    assert (await session.get_graph(equal))[2] == stored_version, "the equal root is not rewritten"
    assert work.version(equal) == stored_version, "and it is held at its stored version"
    assert (await unit(session).get(Book, clash)).label == "Dune", "the other root is stored"


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_is_refused_naming_the_value(session, limit):
    with pytest.raises(ValueError, match=str(limit)):
        limited(session, limit)


async def test_a_failing_batch_keeps_the_conflict_roots_and_adds_the_count_to_the_message(session):
    clash = book_iri(97)
    seeding = unit(session)
    seeding.add(steady_dune(clash).model_copy(update={"label": "Theirs"}))
    await seeding.commit()
    work = limited(session, 2)
    work.add(steady_dune(clash))
    with pytest.raises(Conflict) as raised:
        await work.commit(batches=True)
    assert raised.value.iris == (clash,), "the roots are kept"
    assert "0 of 1 batches committed" in str(raised.value), "the count is in the message"
    assert str(clash) in str(raised.value), "the original message is kept"


async def test_a_failing_batch_keeps_the_arguments_of_a_foreign_exception_and_notes_the_count(
    session, store
):
    work = limited(session, 2)
    work.add(steady_dune(book_iri(98)))
    store.on("update", RuntimeError("x", 42))  # type: ignore[arg-type]
    with pytest.raises(RuntimeError) as raised:
        await work.commit(batches=True)
    assert raised.value.args == ("x", 42), "the arguments are as raised"
    assert any("0 of 1 batches committed" in n for n in raised.value.__notes__), (
        "the count is a note"
    )


async def test_a_failing_batch_extends_only_the_first_argument_of_a_toolkit_error(session, store):
    work = limited(session, 2)
    work.add(steady_dune(book_iri(99)))
    store.on("update", NotFound("gone", 7))
    with pytest.raises(NotFound) as raised:
        await work.commit(batches=True)
    assert raised.value.args[1:] == (7,), "the other arguments are kept"
    assert "gone" in str(raised.value.args[0]), "the first argument is extended"
    assert "0 of 1 batches committed" in str(raised.value.args[0]), "with the count"


# -- discard: take a root out of the pending changes ---------------------------------------------


@pytest.fixture
async def stored_book(session) -> str:
    seeding = unit(session)
    seeding.add(steady_dune(book_iri(114)))
    await seeding.commit()
    return book_iri(114)


async def test_discarding_the_root_a_batch_refused_lets_the_rest_commit(session, store):
    clash = book_iri(110)
    theirs = unit(session)
    theirs.add(steady_dune(clash).model_copy(update={"label": "Theirs"}))
    await theirs.commit()
    work = limited(session, 2)
    for n in (110, 111, 112):
        work.add(steady_dune(book_iri(n)))
    with pytest.raises(Conflict) as refused:
        await work.commit(batches=True)
    for iri in refused.value.iris:
        work.discard(iri)
    await work.commit(batches=True)
    assert (await unit(session).get(Book, clash)).label == "Theirs", "the clashing book is theirs"
    for n in (111, 112):
        label = (await unit(session).get(Book, book_iri(n))).label
        assert label == "Dune", "the other books are stored"
    with pytest.raises(LookupError):
        work.version(clash)


async def test_a_discarded_change_of_a_read_root_is_not_written(session, store, stored_book):
    work = unit(session)
    book = await work.get(Book, stored_book)
    read_at = work.version(stored_book)
    book.label = "Changed"
    work.add(book)
    work.discard(stored_book)
    sent = len(store.sent("update"))
    await work.commit()
    assert len(store.sent("update")) == sent, "nothing is sent"
    assert work.version(stored_book) == read_at, "the root is still held at the version read"


async def test_a_discarded_removal_keeps_the_root_and_it_can_be_added_again(
    session, store, stored_book
):
    work = unit(session)
    book = await work.get(Book, stored_book)
    work.remove(book)
    work.discard(stored_book)
    work.add(book)
    await work.commit()
    assert (await unit(session).get(Book, stored_book)).id == stored_book, "the book is stored"


async def test_discarding_a_root_this_unit_of_work_does_not_hold_is_a_lookup_error(session):
    with pytest.raises(LookupError, match="books"):
        unit(session).discard(book_iri(113))
