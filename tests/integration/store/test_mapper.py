"""The mapper and unit of work against a real Fuseki: the round trip of the toy library (task 2.5)."""

import uuid
from collections.abc import AsyncIterator
from uuid import UUID

import pytest

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import Conflict
from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
)
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import Session, open_session
from tests.fixtures.library.generated.books import Book, Genre
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.fixtures.library.generated.scans import Scan
from tests.toy import ADA, TENANT, access, book_iri, dune, toy_mapper


@pytest.fixture
async def database(store: FusekiStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture
async def session(store: FusekiStore, database: str) -> AsyncIterator[Session]:
    async with open_session(
        store, database=database, tenant_iri=TENANT, principal=Principal(id=ADA)
    ) as opened:
        yield opened


def unit(session: Session) -> UnitOfWork:
    return UnitOfWork(session, toy_mapper())


async def test_a_book_with_chapters_and_notes_comes_back_equal_with_its_tracking(session):
    iri = book_iri(1)
    book = dune(iri)
    work = unit(session)
    work.add(book)
    await work.commit()
    back = await unit(session).get(Book, iri)
    assert back.genre == Genre.FICTION.value, (
        "the enum is stored as its meaning and read as its value"
    )
    assert sorted(c.number for c in back.chapters) == [1, 2], "the chapters nest back"
    assert [len(c.notes) for c in back.chapters] == [1, 1], "each chapter keeps its note"
    assert back.creator == ADA and back.created is not None, "tracking is read from the graph IRI"


async def test_a_scan_keeps_its_reference_to_a_book_as_an_iri(session):
    scan = Scan(
        id=f"{TENANT}/scans/{UUID(int=1)}", label="Scan", description="d", scan_of=book_iri(1)
    )
    work = unit(session)
    work.add(scan)
    await work.commit()
    assert (await unit(session).get(Scan, scan.id)).scan_of == book_iri(1)


async def test_grants_and_prohibitions_round_trip_through_skolem_iris(session):
    record = access(
        grants=[Grant(assignee=ADA, target=TENANT, role="librarian")],
        prohibitions=[Prohibition(assignee=ADA, target=book_iri(1), action=Action.DELETE)],
    )
    work = unit(session)
    work.add(record)
    await work.commit()
    back = await unit(session).get(LibraryAccess, record.id)
    assert (back.grants, back.prohibitions) == (record.grants, record.prohibitions)


async def test_the_tenant_root_lives_in_the_meta_graph(session):
    work = unit(session)
    work.add(Library(id=TENANT, label="City library", description="d", city="Ghent"))
    await work.commit()
    assert (await unit(session).get(Library, TENANT)).city == "Ghent"


async def test_the_part_iris_survive_an_edit_and_a_second_editor_conflicts(session):
    iri = book_iri(2)
    seed = unit(session)
    seed.add(dune(iri))
    await seed.commit()
    one, two = unit(session), unit(session)
    first, second = await one.get(Book, iri), await two.get(Book, iri)
    before = sorted(c.id for c in first.chapters)
    first.label = "edited"
    one.add(first)
    await one.commit()
    second.label = "also edited"
    two.add(second)
    with pytest.raises(Conflict):
        await two.commit()
    assert sorted(c.id for c in (await unit(session).get(Book, iri)).chapters) == before


async def test_editing_the_root_keeps_the_loaded_graphs_and_their_entries(session, store, database):
    iri = book_iri(3)
    ttl = b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .\n'
    loaded = await session.load_graph(iri, ttl, rdf_format=RdfFormat.TURTLE)
    await session.add_graph(iri, list(toy_mapper().to_graph(dune(iri))), [loaded])
    work = unit(session)
    book = await work.get(Book, iri)
    book.label = "Renamed"
    work.add(book)
    await work.commit()
    held = f"ASK {{ GRAPH <{loaded}> {{ ?s ?p ?o }} }}"
    entry = f"ASK {{ GRAPH <{DEFAULT_IRIS.registry(TENANT)}> {{ <{loaded}> ?p ?o }} }}"
    assert (await store.query(database, held)).askAnswer, "the loaded graph keeps its triples"
    assert (await store.query(database, entry)).askAnswer, "and its registry entry"
