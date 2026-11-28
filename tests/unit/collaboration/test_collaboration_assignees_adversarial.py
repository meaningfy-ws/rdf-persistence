"""Adversarial probes of workflow-assignees stage 1 (design D-9) that the happy-path file does not cover.

Each docstring says what the test attacks; "found <defect>" marks a test that failed on its first run.
The helpers and fixtures are those of ``test_collaboration_assignees``.
"""

import pytest

from rdf_persistence import Action, generated_models
from rdf_persistence.collaboration.services.workflows import Workflows
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.exceptions import Forbidden, InvalidBody
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import ADA, MODULES, TENANT, ban, held, role, toy_mapper
from tests.unit.collaboration.assignees_world import (
    LIBRARIAN,
    NONE,
    P1,
    REVIEWER,
    RITA,
    TWO,
    B,
    a_book,
    add,
    assignees_of,
    assigner,
    in_review,
    write_world,
)
from tests.unit.collaboration.collaboration_data import REVIEW, VIEW, version_of


@pytest.fixture
def world(tmp_path):
    return write_world(tmp_path)


@pytest.fixture
def guards(world) -> WriteGuards:
    return WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(VIEW), world.workflows)


@pytest.fixture
async def open_session(guards):
    """The session over a store of its own, with the guard of the assignable workflow."""
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    async with fake_session(store, tenant_iri=TENANT, guards=guards) as session:
        yield session


# (id, the states a librarian moves the book through): where no edge leaving the state carries a reviewer's role
NO_LEAVING_EDGE = [("in-draft", []), ("in-accepted", ["in_review", "accepted"])]


@pytest.mark.parametrize(
    ("path",), [(n[1],) for n in NO_LEAVING_EDGE], ids=[n[0] for n in NO_LEAVING_EDGE]
)
async def test_a_role_on_no_edge_leaving_the_state_cannot_take_the_work(world, open_session, path):
    """Error matrix, 'no role on a leaving edge' (D-3 step 8): the reviewer's role is on an edge, but not one leaving here."""
    session = open_session
    await add(session, a_book())
    lib = assigner(world, session, LIBRARIAN)
    for state in path:
        await lib.transition(B, state, if_version=await version_of(session, B))
    with pytest.raises(Forbidden):
        await assigner(world, session, REVIEWER).assign(
            B, [RITA], if_version=await version_of(session, B)
        )
    assert await assignees_of(session) == NONE, "not taken"


async def test_a_prohibition_comes_before_a_stale_version_conflict(world, open_session):
    """Probe of D-3 steps 3 and 4: the read and Prohibition checks come before the version."""
    session = open_session
    held_version = await in_review(world, session)
    lib = assigner(world, session, LIBRARIAN, bans=[ban(Action.MODIFY, TENANT, ADA)])
    with pytest.raises(Forbidden):
        await lib.assign(B, [P1], if_version=held_version + "-old")


# (id, principal): text that is no IRI that may be stored in a triple
HOSTILE = [
    ("a-space", "https://example.org/people/a b"),
    ("an-angle-bracket", "https://example.org/people/a>b"),
    ("a-newline", "https://example.org/people/a\nb"),
]


async def everyone_reads(principal: str):
    """The ``access_of`` that lets every principal read."""
    return held(role("reader", who=principal))


@pytest.mark.parametrize(("principal"), [h[1] for h in HOSTILE], ids=[h[0] for h in HOSTILE])
async def test_a_principal_that_cannot_be_an_iri_is_refused(world, open_session, principal):
    """Error matrix, 'not an absolute IRI' (D-3 step 5): found a-space-or-angle-bracket-passes-the-IRI-check.

    The check ``_ABSOLUTE`` accepts text no triple can hold; the write then dies with ``SparqlError`` (a 500)
    instead of ``InvalidBody``. The newline case passes only because ``.`` does not match it.
    """
    session = open_session
    held_version = await in_review(world, session)
    lib = assigner(world, session, LIBRARIAN, access_of=everyone_reads)
    with pytest.raises(InvalidBody):
        await lib.assign(B, [principal], if_version=held_version)
    assert await assignees_of(session) == NONE, "nothing stored"


async def test_the_clearing_of_a_workflow_no_longer_assignable_is_still_allowed(
    world, open_session
):
    """Error matrix, 'stops being assignable': assign(iri, []) clears what is stored."""
    session = open_session
    held_version = await in_review(world, session, TWO)
    lib = assigner(world, session, LIBRARIAN, workflow=Workflows([REVIEW], VIEW, world.rules))
    await lib.assign(B, [], if_version=held_version)
    assert await assignees_of(session) == NONE, "cleared"
