"""A consumer's domain service tested with the fakes and no network (rp-testkit: a unit test of a domain service)."""

import socket

import pytest

from rdf_persistence import Conflict, Principal, Session, UnitOfWork
from rdf_persistence.testkit import FakeStore, fake_session, no_network  # noqa: F401  (fixture)
from tests.fixtures.library.generated.books import Book
from tests.toy import ADA, TENANT, book_iri, dune, toy_mapper

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
