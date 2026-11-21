"""The ``collaboration`` fixture and the workflow tests' fixtures; the toy library's documents and session are in ``tests/unit/conftest.py``."""

from collections.abc import AsyncIterator, Callable
from datetime import datetime

import pytest

from rdf_persistence import CallerAccess, VerifiedCaller, generated_models
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import Mapper
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import ADA, BOB, MODULES, ROLES, TOY_SCHEMA, dune, role, toy_mapper
from tests.unit.collaboration.collaboration_data import B1, B2, T0, collab, opened, put


@pytest.fixture
def collaboration(toy_session: Session) -> Callable[..., Collaboration]:
    """Builds a ``Collaboration`` the way ``ServiceKit.collaboration`` does, for a caller and its access."""
    view = load_schema(TOY_SCHEMA)
    rules = AccessRules(load_role_definitions(ROLES))

    def build(
        who: VerifiedCaller,
        access: CallerAccess,
        session: Session | None = None,
        mapper: Mapper | None = None,
    ) -> Collaboration:
        return Collaboration(
            session or toy_session,
            view=view,
            rules=rules,
            iris=DEFAULT_IRIS,
            mapper=mapper or toy_mapper(),
            models=generated_models(*MODULES),
            listings=Listings(view),
            caller=who,
            access=access,
        )

    return build


# -- the fixtures of the workflow tests, shared with the tests that attack them. A module that takes
# -- ``session`` or ``ada`` gives its own ``rules``: the roles it needs.


@pytest.fixture
def now() -> dict[str, datetime]:
    """The time the session's clock tells; a test moves it."""
    return {"t": T0}


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store, now, rules) -> AsyncIterator[Session]:
    async with opened(store, now, ADA, rules) as ada:
        yield ada


@pytest.fixture
async def plain(store, now, rules) -> AsyncIterator[Session]:
    """A session with no workflow guard: what wrote the books before their class named a workflow."""
    async with opened(store, now, ADA, rules, guarded=False) as unguarded:
        yield unguarded


@pytest.fixture
def ada(rules, session) -> Collaboration:
    return collab(rules, session, ADA, role("librarian"))


@pytest.fixture
def bob(rules, session) -> Collaboration:
    return collab(rules, session, BOB, role("reader", who=BOB))


@pytest.fixture
async def books(session: Session) -> None:
    for iri in (B1, B2):
        await put(session, dune(iri, chapters=1))
