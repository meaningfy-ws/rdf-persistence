"""PD-6: the library's models written as YAML by one helper (C1)."""

import yaml

from rdf_persistence.access.domain.generated.rp_access import RoleDefinition
from rdf_persistence.collaboration.domain.generated.rp_workflow import (
    Workflow,
    WorkflowTransition,
)
from rdf_persistence_generation.uml.dump import yaml_text


def test_a_workflow_is_written_in_field_order_with_comment_required_only_when_true():
    workflow = Workflow(
        id="https://example.org/workflows/loan",
        workflow_name="loan",
        workflow_states=["approved", "requested"],
        initial_state="requested",
        workflow_transitions=[
            WorkflowTransition(from_state="requested", to_state="approved", transition_roles=["a"]),
            WorkflowTransition(
                from_state="approved",
                to_state="requested",
                transition_roles=["a"],
                comment_required=True,
            ),
        ],
    )
    data = yaml.safe_load(yaml_text(workflow))
    assert list(data) == [
        "id",
        "workflow_name",
        "workflow_states",
        "initial_state",
        "workflow_transitions",
    ], "the keys follow the model's fields"
    first, second = data["workflow_transitions"]
    assert ("comment_required" in first, second["comment_required"]) == (False, True), (
        "the default is left out, a true value is kept"
    )


def test_roles_are_written_as_a_list_with_plain_strings_for_level_and_actions():
    entry = RoleDefinition(role="librarian", level="tenant", actions=["read", "modify"])
    assert yaml.safe_load(yaml_text([entry])) == [
        {"role": "librarian", "level": "tenant", "actions": ["read", "modify"]}
    ], "a list of models is a YAML list; enums are their values"
