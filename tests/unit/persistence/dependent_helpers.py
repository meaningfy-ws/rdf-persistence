"""What the dependent-write and dependent-diagnosis session tests share: one link of dependence
(a result points at its audit), a store that can act between two calls, the opener and small writers.

Not collected as tests (dependent-aggregates PD-3, PD-4, PD-11).
"""

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

from rdflib import RDF, URIRef

from rdf_persistence.core.domain.exceptions import NotFound
from rdf_persistence.core.domain.generated.rp_core import DependenceLink, Principal
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.session import Session, open_session
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import TENANT

NOW = datetime(2026, 11, 28, tzinfo=UTC)
LIB = "https://example.org/ns/library#"
AUDIT, SPECIAL, OTHER, RESULT, BOOK = (
    URIRef(LIB + name) for name in ("Audit", "SpecialAudit", "Other", "Result", "Book")
)
OF_AUDIT = URIRef(LIB + "of_audit")
LINK = DependenceLink(
    part_classes=[str(RESULT)], pointer=str(OF_AUDIT), whole_classes=[str(AUDIT), str(SPECIAL)]
)
MAX_ROOTS = 10


def iri(kind: str, n: int) -> str:
    return f"{TENANT}/{kind}/{UUID(int=n)}"  # a minted aggregate IRI ends in a UUID


A1, A2 = iri("audits", 1), iri("audits", 2)
R1, R2, R3 = iri("results", 1), iri("results", 2), iri("results", 3)
O1 = iri("others", 1)
ELSEWHERE = "https://elsewhere.example/audits/1"


class RacingStore(FakeStore):
    """A fake store whose next update is preceded by one action of another writer (a fault hook)."""

    def __init__(self) -> None:
        super().__init__()
        self.before_update: Callable[[], Awaitable[None]] | None = None

    async def update(self, dataset: str, sparql: str) -> None:
        if (hook := self.before_update) is not None:
            self.before_update = None
            await hook()
        await super().update(dataset, sparql)


async def new_store() -> RacingStore:
    store = RacingStore()
    await store.create_dataset(FAKE_DATABASE)
    return store


def opened(store: FakeStore, who: str = "ada") -> AbstractAsyncContextManager[Session]:
    return open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=Principal(id=f"https://example.org/people/{who}"),
        clock=lambda: NOW,
        dependence=[LINK],
        limits=LimitSettings(max_roots=MAX_ROOTS),
    )


def audit(root: str, cls: URIRef = AUDIT) -> list:
    return [(URIRef(root), RDF.type, cls)]


def result(root: str, *wholes: str) -> list:
    """A result that points to each of ``wholes`` (one is the legal number)."""
    triples = [(URIRef(root), RDF.type, RESULT)]
    return triples + [(URIRef(root), OF_AUDIT, URIRef(w)) for w in wholes]


async def is_stored(session: Session, root: str) -> bool:
    try:
        await session.get_graph(root)
    except NotFound:
        return False
    return True


def names(error: BaseException, root: str) -> bool:
    """Whether the message of ``error`` names ``root`` (a ``NotFound`` carries no ``iris``)."""
    return root in str(error)
