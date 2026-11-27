"""The fixtures of the assignee tests (workflow-assignees D-8, D-10): an assignable review workflow and its roles.

The shared ``review.workflow.yaml`` and ``library_roles.yaml`` stay as they are, so the tests that append
their own ``reviewer`` keep working. ``write_world`` builds, into a folder, the variant these tests need:
the review workflow with ``assignable: true`` and ``reviewer`` beside ``librarian`` on ``in_review`` ->
``accepted``, a clearing edge, and the roles with ``reviewer`` added at tenant level (``read``, ``annotate``).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from rdf_persistence import AccessRules, load_role_definitions
from rdf_persistence.collaboration.domain.generated.rp_workflow import Workflow
from rdf_persistence.collaboration.services.workflows import Workflows, load_workflow
from tests.toy import REVIEW_WORKFLOW, ROLES
from tests.unit.collaboration.collaboration_data import VIEW

REVIEWER_ROLE = "- {role: reviewer, level: tenant, actions: [read, annotate]}\n"


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
