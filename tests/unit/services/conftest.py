"""The toy library's documents, read once, for the tests of bodies and representations."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from rdf_persistence import CallerAccess, VerifiedCaller
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import fake_session
from tests.toy import ROLES, TENANT, TOY_SCHEMA

GENERATED = Path(__file__).parents[2] / "fixtures" / "library" / "generated"


@pytest.fixture(scope="module")
def documents() -> Documents:
    return Documents(load_schema(TOY_SCHEMA), GENERATED)


@pytest.fixture(scope="module")
def book_class(documents: Documents):
    return documents.aggregates["books"]


@pytest.fixture(scope="module")
def scan_class(documents: Documents):
    return documents.aggregates["scans"]


@pytest.fixture
async def toy_session() -> AsyncIterator[Session]:
    """A session on the toy tenant's database, over the fake store."""
    async with fake_session(tenant_iri=TENANT) as session:
        yield session


@pytest.fixture
def collaboration(toy_session: Session) -> Callable[..., Collaboration]:
    """Builds a ``Collaboration`` the way ``ServiceKit.collaboration`` does, for a caller and its access."""
    view = load_schema(TOY_SCHEMA)
    rules = AccessRules(load_role_definitions(ROLES))

    def build(
        who: VerifiedCaller, access: CallerAccess, session: Session | None = None
    ) -> Collaboration:
        return Collaboration(
            session or toy_session,
            view=view,
            rules=rules,
            iris=DEFAULT_IRIS,
            caller=who,
            access=access,
        )

    return build
