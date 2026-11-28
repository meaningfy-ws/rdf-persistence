"""The fixtures of the assignee tests (workflow-assignees D-8, D-10): an assignable review workflow and its roles.

The shared ``review.workflow.yaml`` and ``library_roles.yaml`` stay as they are, so the tests that append
their own ``reviewer`` keep working. ``write_world`` builds, into a folder, the variant these tests need:
the review workflow with ``assignable: true`` and ``reviewer`` beside ``librarian`` on ``in_review`` ->
``accepted``, a clearing edge, and the roles with ``reviewer`` added at tenant level (``read``, ``annotate``).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from rdf_persistence import AccessRules, generated_models, load_role_definitions
from rdf_persistence.collaboration.domain.generated.rp_workflow import Workflow
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.workflows import Workflows, load_workflow
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.schema.services import vocabulary as v
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    REVIEW_WORKFLOW,
    ROLES,
    book_iri,
    caller,
    dune,
    held,
    role,
    toy_mapper,
)
from tests.unit.collaboration.collaboration_data import VIEW, version_of

REVIEWER_ROLE = "- {role: reviewer, level: tenant, actions: [read, annotate]}\n"

B = book_iri(1)
P1, P2 = "https://example.org/people/p1", "https://example.org/people/p2"
NONE = frozenset()
ONE = frozenset({P1})
TWO = frozenset({P1, P2})
OTHER = frozenset({P2})

RITA = "https://example.org/people/rita"  # holds ``reviewer`` only
NOBODY = "https://example.org/people/nobody"  # no grant at all
OUTSIDER = "not-an-absolute-iri"
LIBRARIAN, REVIEWER, READER, STRANGER = "librarian", "reviewer", "reader", "stranger"


@dataclass(frozen=True)
class AssigneesWorld:
    """The files written for the tests, and what they load into."""

    workflow_file: Path
    roles_file: Path
    workflow: Workflow
    rules: AccessRules

    @property
    def workflows(self) -> Workflows:
        """The workflows of the world, checked against its rules and the toy schema."""
        return Workflows([self.workflow], VIEW, self.rules)


def a_book(assignees=NONE):
    """The book B naming ``assignees`` (none: the slot unset, as an application that knows nothing of them writes it)."""
    return dune(B).model_copy(update={"assigned_to": sorted(assignees) or None})


async def assignees_of(session, iri: str = B) -> frozenset[str]:
    held = await session.root_values(iri, [v.WORKFLOW_ASSIGNEES])
    return frozenset(str(o) for o in held[v.WORKFLOW_ASSIGNEES])


async def replace(session, book, *, allowing: frozenset[str] | None = None) -> None:
    """Replace the stored book; ``allowing`` is what only an assignment or a clearing transition does."""
    version = await version_of(session, str(book.id))
    async with session.transaction() as t:
        if allowing is not None:
            t._allow_assignees(str(book.id), allowing)
        await t.replace_graph(str(book.id), toy_mapper().to_triples(book), version)


async def add(session, book) -> None:
    work = UnitOfWork(session, toy_mapper())
    work.add(book)
    await work.commit()


def access_for(who: str):
    """What the tenant's access record says of ``who``, by the way the test names the caller."""
    return {
        LIBRARIAN: held(role("librarian", who=ADA)),
        REVIEWER: held(role("reviewer", who=RITA)),
        READER: held(role("reader", who=BOB)),
        STRANGER: held(),
    }[who]


PRINCIPAL_OF = {LIBRARIAN: ADA, REVIEWER: RITA, READER: BOB, STRANGER: NOBODY}
# who may read the book, for ``access_of``: the principals the toolkit is asked about
READERS = {
    P1: held(role("reader", who=P1)),
    P2: held(role("reader", who=P2)),
    RITA: held(role("reviewer", who=RITA)),
    ADA: held(role("librarian", who=ADA)),
    NOBODY: held(),
}


async def reads(principal: str):
    """The ``access_of`` of the tests: the stored access of the few principals they know."""
    return READERS[principal]


def assigner(world, session, who: str, *, bans=None, access_of=reads, workflow=True):
    """A ``Collaboration`` for the caller named ``who``; ``workflow=False`` leaves the toy book under none."""
    return Collaboration(
        session,
        view=VIEW,
        rules=world.rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(VIEW),
        workflows=(world.workflows if workflow is True else workflow or None),
        caller=caller(principal=PRINCIPAL_OF[who]),
        access=access_for(who).model_copy(update={"prohibitions": bans}),
        access_of=access_of,
    )


async def in_review(world, session, stored: frozenset[str] = NONE) -> str:
    """The book B in ``in_review``, holding ``stored``; returns its version."""
    await add(session, a_book())
    lib = assigner(world, session, LIBRARIAN)
    await lib.transition(B, "in_review", if_version=await version_of(session, B))
    if stored:
        await replace(session, a_book(stored), allowing=stored)
    return await version_of(session, B)


def assignable_review() -> Workflow:
    """The review workflow, assignable, with a clearing edge for ``librarian`` and ``reviewer`` on acceptance."""
    review = load_workflow(REVIEW_WORKFLOW)
    moves = [
        move.model_copy(
            update={"transition_roles": ["librarian", "reviewer"], "clears_assignees": True}
        )
        if (move.from_state, move.to_state) == ("in_review", "accepted")
        else move
        for move in review.workflow_transitions or []
    ]
    return review.model_copy(update={"assignable": True, "workflow_transitions": moves})


def write_world(folder: Path) -> AssigneesWorld:
    """Write the assignable workflow and the roles file into ``folder`` and load both from there."""
    workflow_file = folder / "assignable.workflow.yaml"
    workflow_file.write_text(
        yaml.safe_dump(assignable_review().model_dump(mode="json", exclude_none=True)),
        encoding="utf-8",
    )
    roles_file = folder / "assignee_roles.yaml"
    roles_file.write_text(ROLES.read_text(encoding="utf-8") + REVIEWER_ROLE, encoding="utf-8")
    return AssigneesWorld(
        workflow_file,
        roles_file,
        load_workflow(workflow_file),
        AccessRules(load_role_definitions(roles_file)),
    )
