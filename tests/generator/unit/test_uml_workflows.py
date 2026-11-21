"""PD-5: a Statechart diagram read as a workflow of the toolkit, one table row for each error-matrix line.

Each row builds a ``UmlModel`` with state nodes, state flows and Statechart diagrams, converts it and checks the
one problem it gives, naming the element, or the report lines a valid diagram gets. The workflows are the
library's own ``Workflow`` records, validated by the library's class; the converted schemas do not change.
"""

import pytest
from linkml_runtime.dumpers import yaml_dumper

from rdf_persistence.collaboration.domain.generated.rp_workflow import (
    Workflow,
    WorkflowTransition,
)
from rdf_persistence_generation.generated.rp_generation import UmlModel
from rdf_persistence_generation.uml.context import Context
from rdf_persistence_generation.uml.workflows import workflow_entries
from tests.generator.uml_model import (
    BOOK,
    METAMODEL_PREFIXES,
    PREFIXES,
    initial,
    klass,
    model,
    run,
    settings,
    state,
    state_flow,
    statechart,
    tag,
)

from .uml_workflow_rows import (
    APPROVED,
    CHART,
    INITIAL,
    LIBRARY,
    OTHER,
    OVERRIDES,
    REQUESTED,
    ROLE_DEFINITION,
    WORKFLOW_ROWS,
    WorkflowRow,
    _loan,
    _uml,
)


@pytest.mark.parametrize("row", [pytest.param(r, id=r.case) for r in WORKFLOW_ROWS])
def test_a_workflow_row(row: WorkflowRow) -> None:
    row.check(run(row.uml, **OVERRIDES))


def _entries(uml: UmlModel, roles=("librarian", "reader")) -> tuple[list[Workflow], Context]:
    ctx = Context(
        settings(**OVERRIDES), METAMODEL_PREFIXES, dict(PREFIXES) | {"lib": LIBRARY, "oth": OTHER}
    )
    return workflow_entries(ctx, uml, roles), ctx


def test_a_class_tagged_with_a_workflow_and_no_statechart_converts_as_today() -> None:
    plain = model(klass(BOOK, "lib:Book"), tags=(tag(BOOK, "workflow", "x"),))
    out = run(plain, **OVERRIDES)
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("workflow") == []
    assert out.klass("app_library", "Book").annotations["workflow"].value == "x"


def test_a_diagram_changes_no_schema() -> None:
    drawn = run(_loan(), **OVERRIDES)
    bare = run(
        model(klass(BOOK, "lib:Book"), klass(ROLE_DEFINITION, "rp:RoleDefinition")), **OVERRIDES
    )
    assert drawn.problems == [], drawn.problem_texts()
    assert {n: yaml_dumper.dumps(s) for n, s in drawn.schemas.items()} == {
        n: yaml_dumper.dumps(s) for n, s in bare.schemas.items()
    }, "the workflows are not part of the schemas"


def test_a_curie_name_gives_the_expanded_iri_and_the_local_name() -> None:
    entries, ctx = _entries(_loan(name="oth:loan"))
    assert ctx.findings.problems() == []
    assert [(e.id, e.workflow_name) for e in entries] == [(f"{OTHER}loan", "loan")]
    assert [r for r in ctx.findings.report() if r.report_kind == "derived_iri"] == [], (
        "a CURIE name needs no derived-iri line"
    )


def test_the_design_example_is_the_workflow_it_yields() -> None:
    nodes = (
        initial(INITIAL),
        state(REQUESTED, "requested"),
        state(APPROVED, "approved"),
        state(53, "refused"),
        state(54, "returned"),
    )
    flows = (
        state_flow(100, INITIAL, REQUESTED),
        state_flow(101, REQUESTED, APPROVED, roles="librarian"),
        state_flow(102, REQUESTED, 53, roles="librarian", comment_required="true"),
        state_flow(103, APPROVED, 54, roles="librarian,reader"),
        state_flow(104, 53, REQUESTED, roles="reader"),
    )
    chart = statechart(CHART, "lib:loan", *(each.object_id for each in nodes))
    entries, ctx = _entries(_uml(nodes, flows, (chart,)))
    assert ctx.findings.problems() == []
    assert entries == [
        Workflow(
            id=f"{LIBRARY}loan",
            workflow_name="loan",
            workflow_states=["approved", "refused", "requested", "returned"],
            initial_state="requested",
            workflow_transitions=[
                WorkflowTransition(
                    from_state="approved",
                    to_state="returned",
                    transition_roles=["librarian", "reader"],
                ),
                WorkflowTransition(
                    from_state="refused", to_state="requested", transition_roles=["reader"]
                ),
                WorkflowTransition(
                    from_state="requested", to_state="approved", transition_roles=["librarian"]
                ),
                WorkflowTransition(
                    from_state="requested",
                    to_state="refused",
                    transition_roles=["librarian"],
                    comment_required=True,
                ),
            ],
        )
    ]
    lines = [r.message for r in ctx.findings.report() if r.report_kind == "workflow"]
    assert lines[0] == "4 states, 4 transitions", "the Initial flow is not a transition"
