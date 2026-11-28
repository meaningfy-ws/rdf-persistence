"""The reader conformance kit: one set of cases, run against the fake and against the real reader (consumer-write-rules PD-14, TC-13)."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from rdf_persistence import Principal, generated_models
from rdf_persistence.collaboration.services.aggregate_validators import (
    AggregateReader,
    AggregateValidators,
)
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.session import GuardContext, open_session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeAggregateReader, FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from rdf_persistence.testkit.reader_conformance import CASES, Case, Seeded
from tests.fixtures.library.domain.generated.books import (
    Book,
    Chapter,
    LendingItem,
    Magazine,
)
from tests.toy import ADA, MODULES, TENANT, TOY_SCHEMA, book_iri, dune, shelf_iri, toy_mapper

UNREADABLE = book_iri(2)
MAGAZINE = f"{TENANT}/magazines/{UUID(int=1)}"
PUBLISHED = date(2020, 1, 1)
AUTHORS = ("Herbert", "Asimov")

SEEDED = Seeded(
    root=Book,
    readable=book_iri(1),
    unreadable=UNREADABLE,
    absent=book_iri(9),
    other=Magazine,
    other_iri=MAGAZINE,
    abstract_parent=LendingItem,
    not_root=Chapter,
    slot="published",
    value=PUBLISHED,
    wrong_value="yesterday",
    text_slot="isbn",
    not_text=5,
    iri_slot="shelf",
    iri_value=shelf_iri(1),
    multi_slot="authors",
    multi_values=AUTHORS,
)


def models() -> list[Book | Magazine]:
    readable = dune(book_iri(1), chapters=0).model_copy(
        update={"published": PUBLISHED, "shelf": shelf_iri(1), "authors": list(AUTHORS)}
    )
    unreadable = dune(UNREADABLE, chapters=0).model_copy(
        update={"published": PUBLISHED, "authors": ["Herbert"]}
    )
    return [readable, unreadable, Magazine(id=MAGAZINE, label="Wired")]


@asynccontextmanager
async def fake_reader() -> AsyncIterator[AggregateReader]:
    yield FakeAggregateReader(models(), roots=[Book, Magazine], unreadable=[UNREADABLE])


@asynccontextmanager
async def real_reader() -> AsyncIterator[AggregateReader]:
    """The real reader over a ``FakeStore`` session with listings, whose ``may_read`` refuses ``unreadable``."""
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    view = load_schema(TOY_SCHEMA)
    async with open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        listings=Listings(view),
        may_read=lambda iri: iri != UNREADABLE,
    ) as session:
        for model in models():
            await session.add_graph(model.id, toy_mapper().to_triples(model))
        loaded = generated_models(*MODULES)
        yield AggregateValidators(view, {}, Path(TOY_SCHEMA).parent).reader(
            session,
            GuardContext(collected={}, rely_on=lambda *_: None, removed=frozenset()),
            lambda name, iri, graph, tracked: toy_mapper().from_graph(
                loaded.named(name), iri, graph, tracked
            ),
        )


READERS: dict[str, Callable[[], AbstractAsyncContextManager[AggregateReader]]] = {
    "fake": fake_reader,
    "real": real_reader,
}


@pytest.mark.parametrize("kind", READERS)
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_reader_keeps_the_contract(case: Case, kind: str):  # TC-13
    async with READERS[kind]() as reader:
        await case(reader, SEEDED)


def test_the_kit_lists_each_case_of_the_contract():
    assert len(CASES) == len({case.__name__ for case in CASES}) >= 14, "named and distinct"
