"""A consumer's domain service tested with the fakes and no network (rp-testkit: a unit test of a domain service)."""

import socket

import pytest

from rdf_persistence import Conflict, Principal, Session, UnitOfWork
from rdf_persistence.domain.exceptions import BadQuery, InvalidIri
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.testkit import FakeStore, fake_session, no_network  # noqa: F401  (fixture)
from tests.fixtures.library.generated.books import Book
from tests.toy import ADA, SETTINGS, TENANT, TOY_SCHEMA, book_iri, dune, toy_mapper
from tests.toy_service import CONSUMER_POLICY

BEN = "https://example.org/people/ben"


async def rename(session: Session, iri: str, label: str) -> None:
    """A consumer's domain service: change a book's label, through the unit of work."""
    work = UnitOfWork(session, toy_mapper())
    book = await work.get(Book, iri)
    book.label = label
    work.add(book)
    await work.commit()


async def read(session: Session, iri: str) -> Book:
    return await UnitOfWork(session, toy_mapper()).get(Book, iri)


async def test_a_domain_service_runs_over_the_fake_session_with_no_network(no_network):  # noqa: F811
    async with fake_session(tenant_iri=TENANT) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(dune(book_iri(1)))
        await work.commit()
        await rename(session, book_iri(1), "Dune Messiah")
        assert (await read(session, book_iri(1))).label == "Dune Messiah"
    with pytest.raises(RuntimeError, match="network"):
        socket.create_connection(("127.0.0.1", 9))


async def test_the_fake_session_commits_as_the_given_principal_and_keeps_the_guard(no_network):  # noqa: F811
    async with fake_session(tenant_iri=TENANT, principal=Principal(id=BEN)) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(dune(book_iri(1)))
        await work.commit()
        _, _, stale = await session.get_graph(book_iri(1))
        await rename(session, book_iri(1), "Dune Messiah")
        assert (await read(session, book_iri(1))).creator == BEN, "tracked as the principal"
        with pytest.raises(Conflict):
            await session.replace_graph(book_iri(1), [], stale)


async def test_two_fake_sessions_over_one_store_see_the_same_data(no_network):  # noqa: F811
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT, principal=Principal(id=ADA)) as ada:
        work = UnitOfWork(ada, toy_mapper())
        work.add(dune(book_iri(1)))
        await work.commit()
    async with fake_session(store, tenant_iri=TENANT, principal=Principal(id=BEN)) as ben:
        assert (await read(ben, book_iri(1))).creator == ADA


# --- fake_session under a consumer's IRI policy (iri-policy task 3.4) -------------------------------


def _consumer_iris() -> Iris:
    settings = SETTINGS.model_copy(update={"iri_policy": CONSUMER_POLICY})
    return Iris(settings, *iri_types(load_schema(TOY_SCHEMA)))


async def test_the_fake_session_takes_the_iris_a_consumer_policy_mints(no_network):  # noqa: F811
    iris = _consumer_iris()
    tenant = str(iris.tenant("p4x8k2m"))
    flat_book = str(iris.aggregate(tenant, "book", "books", "abcdefghijklm"))
    async with fake_session(tenant_iri=tenant, iris=iris) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(dune(flat_book))
        await work.commit()
        assert (await read(session, flat_book)).label == "Dune"


async def test_the_fake_session_without_iris_refuses_what_only_a_consumer_policy_mints(
    no_network,  # noqa: F811
):
    iris = _consumer_iris()
    tenant = str(iris.tenant("p4x8k2m"))
    flat_book = str(iris.aggregate(tenant, "book", "books", "abcdefghijklm"))
    async with fake_session(tenant_iri=tenant) as session:
        with pytest.raises(InvalidIri):
            await session.add_graph(flat_book, [])


# --- the fake store applies one update request as one transaction (atomic-commit PD-13, TC-14) ------

NAME = "atomic"
INSERT_THEN_CREATE_EXISTING = (
    "INSERT DATA { GRAPH <urn:g:one> { <urn:s> <urn:p> <urn:o> } } ; CREATE GRAPH <urn:g:two>"
)
# rdflib refuses CREATE of a graph that holds nothing ("not implemented"), so the existing one has a triple
EXISTING = "INSERT DATA { GRAPH <urn:g:two> { <urn:s> <urn:p> <urn:x> } }"
TWO_INSERTS = (
    "INSERT DATA { GRAPH <urn:g:one> { <urn:s> <urn:p> <urn:o> } } ;"
    " INSERT DATA { GRAPH <urn:g:three> { <urn:s> <urn:p> <urn:o> } }"
)
SEEN = "ASK { GRAPH <urn:g:one> { <urn:s> <urn:p> <urn:o> } }"


async def test_tc14_a_request_whose_second_operation_fails_leaves_the_first_unapplied():
    store = FakeStore()
    await store.create_dataset(NAME)
    await store.update(NAME, EXISTING)
    with pytest.raises(BadQuery):
        await store.update(NAME, INSERT_THEN_CREATE_EXISTING)
    assert not (await store.query(NAME, SEEN)).askAnswer, "the insert must not be visible"


async def test_a_request_that_succeeds_is_applied_whole():
    store = FakeStore()
    await store.create_dataset(NAME)
    await store.update(NAME, TWO_INSERTS)
    assert (await store.query(NAME, SEEN)).askAnswer


async def test_the_after_update_hook_runs_after_a_successful_update_and_before_the_return():
    store = FakeStore()
    await store.create_dataset(NAME)
    seen = []

    async def hook() -> None:
        seen.append((await store.query(NAME, SEEN)).askAnswer)

    store.after_update = hook
    await store.update(NAME, TWO_INSERTS)
    assert seen == [True], "the hook saw the update applied"


async def test_the_after_update_hook_does_not_run_when_the_update_fails():
    store = FakeStore()
    await store.create_dataset(NAME)
    await store.update(NAME, EXISTING)
    ran = []

    async def hook() -> None:
        ran.append(True)

    store.after_update = hook
    with pytest.raises(BadQuery):
        await store.update(NAME, INSERT_THEN_CREATE_EXISTING)
    assert ran == []
