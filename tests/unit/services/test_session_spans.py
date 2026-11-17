"""The commit of a transaction is one span, and only when there is something to commit (otel-observability PD-5): TC-29 to TC-31."""

from collections.abc import AsyncIterator

import pytest
from opentelemetry.trace import StatusCode
from rdflib import Literal, URIRef

from rdf_persistence.domain.exceptions import Conflict
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.services.session import Session, open_session
from rdf_persistence.services.store import ToolkitStore, TracedStore
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import ADA, TENANT, book_iri

BOOK = book_iri(1)
TITLE = URIRef("http://purl.org/dc/terms/title")
COMMIT = "rp.session.commit"


def title(text: str) -> list:
    return [(URIRef(BOOK), TITLE, Literal(text))]


@pytest.fixture
async def session() -> AsyncIterator[Session]:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    store = ToolkitStore(TracedStore(fake, "rdflib"))
    async with open_session(
        store, database=FAKE_DATABASE, tenant_iri=TENANT, principal=Principal(id=ADA)
    ) as opened:
        yield opened


async def test_tc29_a_commit_is_one_span_with_the_tenant_database_and_the_store_update_inside(
    session, spans
):
    async with session.transaction() as transaction:
        await transaction.add_graph(BOOK, title("Dune"))
    (commit,) = [s for s in spans() if s.name == COMMIT]
    assert commit.attributes["rp.step"] == "commit", "the step"
    assert commit.attributes["db.namespace"] == FAKE_DATABASE, "the tenant database"
    updates = [s for s in spans() if s.name == "update"]
    assert updates, "the store was called through the traced store"
    inside = [s for s in updates if s.parent and s.parent.span_id == commit.context.span_id]
    assert inside, "the store's update span is a child of the commit span"
    assert inside[0].context.trace_id == commit.context.trace_id, "in one trace"


async def test_tc30_a_commit_with_no_roots_opens_no_span(session, spans):
    async with session.transaction():
        pass
    assert [s for s in spans() if s.name == COMMIT] == [], "nothing to commit, no span"


async def test_tc31_a_commit_that_raises_conflict_marks_its_span_with_the_error_type(
    session, spans
):
    await session.add_graph(BOOK, title("Dune"))
    with pytest.raises(Conflict):
        async with session.transaction() as transaction:
            await transaction.add_graph(BOOK, title("again"))
    *_, commit = [s for s in spans() if s.name == COMMIT]  # the last: the seed's commit came first
    assert commit.status.status_code == StatusCode.ERROR, "the span is ERROR"
    assert commit.attributes["error.type"].endswith("Conflict"), "the error type names Conflict"
