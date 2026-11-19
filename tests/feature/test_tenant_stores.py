"""Steps of ``tenant_stores.feature``: tenants on two ``FakeStore`` servers, through the services (tenant-stores 2.3).

Scenario to spec scenario (``rp-tenancy``): "two libraries on two servers" is "two tenants on two stores";
"recorded before servers had names" is "an existing record"; "deleted library" is "deletion on the tenant's
store"; "a leftover on another server" is "an orphan on another store"; "no longer wired" is "a store that is
no longer wired"; "copied by dump and restore" is "a copy on another store". The other three scenarios of
the spec are unit tests (TC-15, TC-16, TC-26).
"""

import asyncio
import io

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib import URIRef

from rdf_persistence.core.domain.exceptions import StoreNotWired
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.sparql import fill, term
from rdf_persistence.iris.domain.layout import graph_iri, tenant_name_prefix
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.migrations.services.migrations import chain_of
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import iri_types
from rdf_persistence.schema.services.vocabulary import TOOLKIT_MIGRATIONS, metamodel
from rdf_persistence.tenancy.services.sweep import sweep
from rdf_persistence.tenancy.services.tenancy import DEFAULT_STORE, Tenancy
from rdf_persistence.tenancy.services.tenant_dump import dump, restore
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.domain.generated.books import Book
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.toy import (
    ADA,
    BOB,
    SETTINGS,
    TOY_MIGRATIONS,
    TOY_SCHEMA,
    dune,
    library_slots,
    toy_mapper,
)

scenarios("tenant_stores.feature")

LIBRARY_SCHEMA = "https://example.org/ns/library"
VIEW = load_schema(TOY_SCHEMA)
TYPES = iri_types(VIEW)
CHAINS = [chain_of(metamodel(), TOOLKIT_MIGRATIONS), chain_of(VIEW, TOY_MIGRATIONS)]
ASK = "ASK { GRAPH $g { ?s ?p ?o } }"
PREFIX = tenant_name_prefix(SETTINGS.prefix)
OWNERS = {"Ada": Principal(id=ADA), "Bob": Principal(id=BOB)}


class Run:
    """The stores and the files the scenario shares across service starts, and what it has seen."""

    def __init__(self) -> None:
        self.stores: dict[str, FakeStore] = {DEFAULT_STORE: FakeStore()}
        self.files = FakeFileStore()
        self.tenancy: Tenancy
        self.tenants: dict[str, str] = {}
        self.books: dict[str, str] = {}
        self.orphan = ""
        self.refused: StoreNotWired | None = None
        self.copy = ""
        self.opened: FakeStore | None = None
        self.database = ""
        self.main_before: list[str] = []

    def go(self, work):
        return asyncio.run(work)

    def wire(self, *names: str) -> Tenancy:
        """A tenancy (a service that has just started) over the main store and the named ones."""
        for name in names:
            self.stores.setdefault(name, FakeStore())
        self.tenancy = Tenancy(
            self.stores[DEFAULT_STORE],
            self.files,
            SETTINGS,
            mapper=toy_mapper(),
            root_class=Library,
            access_class=LibraryAccess,
            iris=Iris(SETTINGS, *TYPES),
            stamps=[
                (metamodel().schema.id, metamodel().schema.version),
                (LIBRARY_SCHEMA, "1"),
            ],
            stores={name: self.stores[name] for name in names},
        )
        return self.tenancy

    async def create(self, owner: str, store: str) -> None:
        await self.tenancy.ensure_system_database()
        summary = await self.tenancy.create("Ghent", library_slots(), OWNERS[owner], store=store)
        self.tenants[owner] = summary.id

    async def write_book(self, owner: str) -> None:
        tenant = self.tenants[owner]
        book = str(Iris(SETTINGS, *TYPES).mint_aggregate(tenant, "book", "books"))
        async with self.tenancy.tenant_session(tenant, OWNERS[owner]) as session:
            work = UnitOfWork(session, toy_mapper())
            work.add(dune(book))
            await work.commit()
        self.books[owner] = book

    async def reads_back(self, tenant: str, owner: str, book: str) -> bool:
        async with self.tenancy.tenant_session(tenant, OWNERS[owner]) as session:
            return isinstance(await UnitOfWork(session, toy_mapper()).get(Book, book), Book)

    async def holds(self, store: str, tenant: str, book: str) -> bool:
        database = self.tenancy.database_of(tenant)
        answer = await self.stores[store].query(
            database, fill(ASK, g=term(URIRef(graph_iri(book))))
        )
        return bool(answer.askAnswer)

    async def databases(self, store: str) -> list[str]:
        """The tenant databases on ``store`` (the system database is not one)."""
        return [
            name for name in await self.stores[store].list_datasets() if name.startswith(PREFIX)
        ]


@pytest.fixture
def run() -> Run:
    return Run()


@given(parsers.parse('the service is wired to the main server and to the server "{name}"'))
def _wired(run: Run, name: str) -> None:
    run.wire(name)


@given(parsers.parse("{owner}'s library is created on the main server"))
def _created_on_main(run: Run, owner: str) -> None:
    run.go(run.create(owner, DEFAULT_STORE))


@given(parsers.parse('{owner}\'s library is created on "{store}"'))
def _created_on(run: Run, owner: str, store: str) -> None:
    run.go(run.create(owner, store))


@given(parsers.parse('{owner}\'s library is created on "{store}" and holds a book'))
def _created_with_book(run: Run, owner: str, store: str) -> None:
    run.go(run.create(owner, store))
    run.go(run.write_book(owner))


@given(
    parsers.parse('{owner}\'s library was created on "{store}" while the service was wired to it')
)
def _created_while_wired(run: Run, owner: str, store: str) -> None:
    run.wire("client-a", store)
    run.go(run.create(owner, store))


@given(parsers.parse("{owner}'s library was recorded before servers had names"))
def _recorded_before(run: Run, owner: str) -> None:
    # a library on the main server has no server name in its record: the record an old service wrote
    run.go(run.create(owner, DEFAULT_STORE))


@given(parsers.parse('"{store}" holds a library that no one owns'))
def _orphan(run: Run, store: str) -> None:
    run.orphan = PREFIX + "0" * 32
    run.go(run.stores[store].create_dataset(run.orphan))


@given(parsers.parse('the service is now wired to the main server and to the server "{name}"'))
def _now_wired(run: Run, name: str) -> None:
    run.wire(name)


@when("a book is written to each library")
def _write_books(run: Run) -> None:
    for owner in ("Ada", "Bob"):
        run.go(run.write_book(owner))


@when("Bob's library is deleted")
def _delete_bob(run: Run) -> None:
    async def delete() -> None:
        tenant = run.tenants["Bob"]
        run.main_before = await run.stores[DEFAULT_STORE].list_datasets()
        run.database = run.tenancy.database_of(tenant)
        _, version = await run.tenancy.get(tenant)
        await run.tenancy.delete(tenant, version)

    run.go(delete())


@when("Ada's library is read by a service that has just started")
def _cold_read(run: Run) -> None:
    run.wire("client-a")
    run.opened = run.go(run.tenancy.store_of(run.tenants["Ada"]))


@when("the service starts")
def _starts(run: Run) -> None:
    async def start() -> None:
        try:
            await sweep(run.tenancy, run.stores[DEFAULT_STORE], run.files, SETTINGS)
        except StoreNotWired as refusal:
            run.refused = refusal

    run.go(start())


@when("Bob's library is dumped and the dump is restored on the main server")
def _dump_restore(run: Run) -> None:
    async def copy() -> None:
        tenant = run.tenants["Bob"]
        iris = Iris(SETTINGS, *TYPES)
        out = io.BytesIO()
        source = await run.tenancy.store_of(tenant)
        await dump(run.tenancy, source, run.files, iris, VIEW, tenant, out)
        summary = await restore(
            run.tenancy,
            iris,
            VIEW,
            io.BytesIO(out.getvalue()),
            OWNERS["Bob"],
            max_bytes=1 << 30,
            chains=CHAINS,
        )
        run.copy = summary.id

    run.go(copy())


@then("each book is stored only on its own library's server")
def _stored_apart(run: Run) -> None:
    on = {"Ada": DEFAULT_STORE, "Bob": "client-a"}
    for owner, store in on.items():
        tenant = run.tenants[owner]
        assert run.go(run.holds(store, tenant, run.books[owner])), f"{owner}'s book is on {store}"
        assert run.go(run.databases(store)) == [run.tenancy.database_of(tenant)], (
            f"{store} holds {owner}'s library and no other"
        )


@then("each book reads back from its own library")
def _read_back(run: Run) -> None:
    for owner in ("Ada", "Bob"):
        assert run.go(run.reads_back(run.tenants[owner], owner, run.books[owner])), (
            f"{owner}'s book reads back"
        )


@then("the library opens on the main server")
def _opens_on_main(run: Run) -> None:
    assert run.opened is run.stores[DEFAULT_STORE], "the main server's store opened it"


@then(parsers.parse('Bob\'s library is gone from "{store}"'))
def _gone_from(run: Run, store: str) -> None:
    assert run.database not in run.go(run.stores[store].list_datasets()), f"gone from {store}"


@then("nothing is removed from the main server")
def _main_untouched(run: Run) -> None:
    now = run.go(run.stores[DEFAULT_STORE].list_datasets())
    assert now == run.main_before, "the main server's databases are as before"


@then(parsers.parse('the library that no one owns is removed from "{store}"'))
def _orphan_removed(run: Run, store: str) -> None:
    assert run.orphan not in run.go(run.stores[store].list_datasets()), f"gone from {store}"


@then(parsers.parse('Bob\'s library is still on "{store}"'))
def _bob_kept(run: Run, store: str) -> None:
    database = run.tenancy.database_of(run.tenants["Bob"])
    assert database in run.go(run.stores[store].list_datasets()), f"still on {store}"


@then("Bob's book is still in it")
def _bob_book_kept(run: Run) -> None:
    held = run.go(run.holds("client-a", run.tenants["Bob"], run.books["Bob"]))
    assert held, "Bob's book is still in his library"


@then(parsers.parse('the start-up is refused, naming "{store}"'))
def _refused(run: Run, store: str) -> None:
    assert run.refused is not None, "the start-up was not refused"
    assert store in str(run.refused), f"the refusal names {store}"


@then(parsers.parse('the library that no one owns is still on "{store}"'))
def _orphan_kept(run: Run, store: str) -> None:
    assert run.orphan in run.go(run.stores[store].list_datasets()), f"still on {store}"


@then("a new library with a new address exists")
def _copy_is_new(run: Run) -> None:
    assert run.copy, "a library was restored"
    assert run.copy != run.tenants["Bob"], "its address is not Bob's library's"


@then("the new library lives on the main server")
def _copy_on_main(run: Run) -> None:
    main = run.stores[DEFAULT_STORE]
    assert run.go(run.tenancy.store_of(run.copy)) is main, "its tenancy routes to the main store"
    assert run.tenancy.database_of(run.copy) in run.go(main.list_datasets()), (
        "its database is there"
    )


@then("the book reads back from the new library")
def _copy_reads(run: Run) -> None:
    moved = run.books["Bob"].replace(run.tenants["Bob"], run.copy)  # the book's address in the copy
    assert run.go(run.reads_back(run.copy, "Bob", moved)), "the book reads back from the copy"
