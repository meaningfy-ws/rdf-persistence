"""What the referenced-removal session tests share: the refusal stub, the opener and two small readers.

Not collected as tests; ``test_session_referenced_removal`` and its ``_dependents`` import from here.
"""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from rdflib import RDF, URIRef

from rdf_persistence import InUse
from rdf_persistence.core.domain.exceptions import NotFound
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.persistence.services.generated.rows.rp_persistence_rows import ReferrerRow
from rdf_persistence.persistence.services.referrers import Dependents
from rdf_persistence.persistence.services.session import Session, open_session
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import AUTHOR, TENANT

NOW = datetime(2026, 11, 20, tzinfo=UTC)


class StubRefusal:
    """The schema side of a removal refusal: what the session asks, kept for the tests to read."""

    def __init__(
        self, refusing: frozenset[URIRef] = frozenset({AUTHOR}), call_readable: bool = False
    ) -> None:
        self.refusing = refusing
        self.call_readable = call_readable
        # (roots, rows, readable, the root the rows refer to), per call
        self.asked: list[tuple[tuple[str, ...], list[ReferrerRow], object, str]] = []

    async def in_use(
        self, roots: Sequence[str], root: str, rows: Sequence[ReferrerRow], readable
    ) -> InUse:
        self.asked.append((tuple(roots), list(rows), readable, root))
        if self.call_readable and readable is not None:
            await readable(root, rows)
        named = tuple((row.referrer, "Book", "written_by") for row in rows)
        return InUse("in use", iris=tuple(roots), referrers=named)


def opened(
    store: FakeStore,
    removals: StubRefusal | None,
    who: str = "ada",
    dependents: Dependents = (),
) -> AbstractAsyncContextManager[Session]:
    return open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=Principal(id=f"https://example.org/people/{who}"),
        clock=lambda: NOW,
        removals=removals,
        dependents=dependents,
    )


def author(iri: str, *more: URIRef) -> list:
    return [(URIRef(iri), RDF.type, c) for c in (AUTHOR, *more)]


async def stored(session: Session, iri: str) -> bool:
    try:
        await session.get_graph(iri)
    except NotFound:
        return False
    return True
