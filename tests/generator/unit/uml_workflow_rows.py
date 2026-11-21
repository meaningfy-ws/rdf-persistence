"""The workflow rows of the UML error matrix, shared by ``test_uml_workflows`` and ``test_uml_rules``."""

from collections.abc import Callable
from dataclasses import dataclass

from rdf_persistence_generation.generated.rp_generation import UmlModel, UmlPrefix, UmlRule
from tests.generator.uml_model import (
    BOOK,
    PREFIXES,
    Converted,
    initial,
    klass,
    model,
    object_,
    other_node,
    state,
    state_flow,
    statechart,
    tag,
)

ROLE_DEFINITION = 30  # the drawn toolkit class rp:RoleDefinition
LIBRARY = "https://example.org/ns/library/"
OTHER = "https://example.org/ns/other/"
OVERRIDES = {
    "prefixes": [
        UmlPrefix(prefix_name=name, namespace=namespace)
        for name, namespace in {**PREFIXES, "lib": LIBRARY, "oth": OTHER}.items()
    ]
}
INITIAL, REQUESTED, APPROVED = 50, 51, 52
SECOND_INITIAL, WAITING = 60, 61
CHART, SECOND_CHART = 70, 71
Check = Callable[[Converted], None]


@dataclass(frozen=True)
class WorkflowRow:
    """One case of the error matrix: the model drawn and what must hold of its run."""

    case: str
    rule: UmlRule
    uml: UmlModel
    check: Check


def _roles():
    return tuple(
        object_(
            40 + n, name, ROLE_DEFINITION, ("role", name), ("level", "tenant"), ("actions", "read")
        )
        for n, name in enumerate(("librarian", "reader"))
    )


def _uml(nodes, flows, charts, *, tags=()):
    return model(
        klass(BOOK, "lib:Book"),
        klass(ROLE_DEFINITION, "rp:RoleDefinition"),
        objects=_roles(),
        state_nodes=tuple(nodes),
        state_flows=tuple(flows),
        statecharts=tuple(charts),
        tags=tuple(tags),
    )


def _base_nodes():
    return (initial(INITIAL), state(REQUESTED, "requested"), state(APPROVED, "approved"))


def _loan(*, nodes=(), flows=(), tags=(), name="lib:loan"):
    """A valid diagram (Initial, ``requested``, ``approved``) with the nodes and flows a row adds."""
    placed = (INITIAL, REQUESTED, APPROVED, *(each.object_id for each in nodes))
    return _uml(
        (*_base_nodes(), *nodes),
        (
            state_flow(100, INITIAL, REQUESTED),
            state_flow(101, REQUESTED, APPROVED, roles="librarian"),
            *flows,
        ),
        (statechart(CHART, name, *placed),),
        tags=tags,
    )


def _asking(**tags: str):
    """The diagram whose one transition ``requested -> approved`` carries exactly these tags."""
    return _uml(
        _base_nodes(),
        (state_flow(100, INITIAL, REQUESTED), state_flow(101, REQUESTED, APPROVED, **tags)),
        (statechart(CHART, "lib:loan", INITIAL, REQUESTED, APPROVED),),
    )


def _lacking(*, node=None, flow=None):
    """The diagram with a node, or a flow, taken away."""
    nodes = tuple(each for each in _base_nodes() if each.object_id != node)
    flows = tuple(
        each
        for each in (
            state_flow(100, INITIAL, REQUESTED),
            state_flow(101, REQUESTED, APPROVED, roles="librarian"),
        )
        if each.connector_id != flow
    )
    return _uml(nodes, flows, (statechart(CHART, "lib:loan", *(each.object_id for each in nodes)),))


def _with_second(*, first=None, name="oth:other", flows=(), placed=(SECOND_INITIAL, WAITING)):
    """The first diagram and a second, valid one (Initial -> ``waiting``) beside it."""
    base = first or _loan()
    return _uml(
        (*base.uml_state_nodes, initial(SECOND_INITIAL, "start"), state(WAITING, "waiting")),
        (*base.uml_state_flows, state_flow(110, SECOND_INITIAL, WAITING), *flows),
        (*base.uml_statecharts, statechart(SECOND_CHART, name, *placed)),
    )


def _problem(rule: UmlRule, *fragments: str) -> Check:
    """The run fails with exactly one problem, of this rule, whose text holds every fragment."""

    def check(out: Converted) -> None:
        assert [p.rule for p in out.problems] == [rule.value], out.problem_texts()
        for fragment in fragments:
            assert fragment in out.problem_texts()[0], (
                f"the problem must say {fragment!r}: {out.problem_texts()}"
            )

    return check


def _valid(out: Converted) -> None:
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("workflow") == [
        "lib:loan: 2 states, 1 transitions",
        "lib:loan: named by no class",
    ], out.report


def _plain(out: Converted) -> None:
    iri = f"{LIBRARY}workflows/loan"
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("derived_iri") == [
        f"loan: the IRI {iri} is derived from the diagram name"
    ]


def _named(out: Converted) -> None:
    assert out.problems == [], out.problem_texts()
    assert out.report_lines("workflow") == ["lib:loan: 2 states, 1 transitions"], out.report


WORKFLOW_ROWS = [
    WorkflowRow("a valid diagram", UmlRule.WORKFLOW_DEFINITION, _loan(), _valid),
    WorkflowRow(
        "a StateNode that is not Initial is no rule",
        UmlRule.NO_RULE,
        _loan(nodes=(other_node(55, "closed", 4),)),
        _problem(UmlRule.NO_RULE, "closed", "StateNode kind 4"),
    ),
    WorkflowRow(
        "a state on no Statechart diagram",
        UmlRule.WORKFLOW_NODE,
        _uml(
            (*_base_nodes(), state(55, "lost")),
            (
                state_flow(100, INITIAL, REQUESTED),
                state_flow(101, REQUESTED, APPROVED, roles="librarian"),
            ),
            (statechart(CHART, "lib:loan", INITIAL, REQUESTED, APPROVED),),
        ),
        _problem(UmlRule.WORKFLOW_NODE, "lost"),
    ),
    WorkflowRow(
        "a state on two Statechart diagrams",
        UmlRule.WORKFLOW_NODE,
        _with_second(placed=(SECOND_INITIAL, WAITING, APPROVED)),
        _problem(UmlRule.WORKFLOW_NODE, "approved", "lib:loan", "oth:other"),
    ),
    WorkflowRow(
        "no Initial node",
        UmlRule.WORKFLOW_INITIAL,
        _lacking(node=INITIAL, flow=100),
        _problem(UmlRule.WORKFLOW_INITIAL, "lib:loan"),
    ),
    WorkflowRow(
        "two Initial nodes",
        UmlRule.WORKFLOW_INITIAL,
        _loan(nodes=(initial(55, "again"),), flows=(state_flow(102, 55, APPROVED),)),
        _problem(UmlRule.WORKFLOW_INITIAL, "lib:loan"),
    ),
    WorkflowRow(
        "an Initial node with no outgoing flow",
        UmlRule.WORKFLOW_INITIAL,
        _lacking(flow=100),
        _problem(UmlRule.WORKFLOW_INITIAL, "lib:loan"),
    ),
    WorkflowRow(
        "an Initial node with two outgoing flows",
        UmlRule.WORKFLOW_INITIAL,
        _loan(flows=(state_flow(102, INITIAL, APPROVED),)),
        _problem(UmlRule.WORKFLOW_INITIAL, "lib:loan"),
    ),
    WorkflowRow(
        "an Initial flow that carries a tag",
        UmlRule.WORKFLOW_INITIAL,
        _uml(
            _base_nodes(),
            (
                state_flow(100, INITIAL, REQUESTED, roles="reader"),
                state_flow(101, REQUESTED, APPROVED, roles="librarian"),
            ),
            (statechart(CHART, "lib:loan", INITIAL, REQUESTED, APPROVED),),
        ),
        _problem(UmlRule.WORKFLOW_INITIAL, "initial -> requested"),
    ),
    WorkflowRow(
        "a diagram name with an unknown prefix",
        UmlRule.CLASS_IRI,
        _loan(name="zz:loan"),
        _problem(UmlRule.CLASS_IRI, "zz"),
    ),
    WorkflowRow(
        "a plain diagram name is written", UmlRule.WORKFLOW_DEFINITION, _loan(name="loan"), _plain
    ),
    WorkflowRow(
        "a diagram name that breaks the workflow name pattern",
        UmlRule.WORKFLOW_DEFINITION,
        _loan(name="Loan_Flow"),
        _problem(UmlRule.WORKFLOW_DEFINITION, "Loan_Flow", "workflow_name"),
    ),
    WorkflowRow(
        "two states with one name",
        UmlRule.WORKFLOW_DEFINITION,
        _loan(nodes=(state(55, "approved"),)),
        _problem(UmlRule.WORKFLOW_DEFINITION, "lib:loan", "approved"),
    ),
    WorkflowRow(
        "a state name that breaks the state pattern",
        UmlRule.WORKFLOW_DEFINITION,
        _loan(nodes=(state(55, "On Loan"),)),
        _problem(UmlRule.WORKFLOW_DEFINITION, "lib:loan", "workflow_states", "On Loan"),
    ),
    WorkflowRow(
        "a tag other than roles and comment_required",
        UmlRule.WORKFLOW_TRANSITION,
        _asking(roles="librarian", colour="red"),
        _problem(UmlRule.WORKFLOW_TRANSITION, "requested -> approved", "colour"),
    ),
    WorkflowRow(
        "comment_required that is not true or false",
        UmlRule.WORKFLOW_TRANSITION,
        _asking(roles="librarian", comment_required="yes"),
        _problem(UmlRule.WORKFLOW_TRANSITION, "requested -> approved", "comment_required", "yes"),
    ),
    WorkflowRow(
        "a transition with no roles",
        UmlRule.WORKFLOW_TRANSITION,
        _asking(),
        _problem(UmlRule.WORKFLOW_TRANSITION, "requested -> approved", "roles"),
    ),
    WorkflowRow(
        "roles with none left after splitting",
        UmlRule.WORKFLOW_TRANSITION,
        _asking(roles=" , "),
        _problem(UmlRule.WORKFLOW_TRANSITION, "requested -> approved", "roles"),
    ),
    WorkflowRow(
        "a role no role object draws",
        UmlRule.WORKFLOW_TRANSITION,
        _asking(roles="librarian, janitor"),
        _problem(UmlRule.WORKFLOW_TRANSITION, "requested -> approved", "janitor"),
    ),
    WorkflowRow(
        "a transition into the Initial node",
        UmlRule.WORKFLOW_TRANSITION,
        _loan(flows=(state_flow(102, APPROVED, INITIAL, roles="reader"),)),
        _problem(UmlRule.WORKFLOW_TRANSITION, "approved -> initial"),
    ),
    WorkflowRow(
        "a transition across diagrams",
        UmlRule.WORKFLOW_TRANSITION,
        _with_second(flows=(state_flow(120, REQUESTED, WAITING, roles="reader"),)),
        _problem(UmlRule.WORKFLOW_TRANSITION, "requested -> waiting"),
    ),
    WorkflowRow(
        "two transitions with one source and target",
        UmlRule.WORKFLOW_TRANSITION,
        _loan(flows=(state_flow(102, REQUESTED, APPROVED, roles="reader"),)),
        _problem(UmlRule.WORKFLOW_TRANSITION, "requested -> approved"),
    ),
    WorkflowRow(
        "a class tagged with a workflow no diagram draws",
        UmlRule.WORKFLOW_CLASS,
        _loan(tags=(tag(BOOK, "workflow", "other"),)),
        _problem(UmlRule.WORKFLOW_CLASS, "Book", "other"),
    ),
    WorkflowRow(
        "a class tagged with a workflow a diagram draws",
        UmlRule.WORKFLOW_CLASS,
        _loan(tags=(tag(BOOK, "workflow", "loan"),)),
        _named,
    ),
    WorkflowRow(
        "two diagrams with one workflow name",
        UmlRule.WORKFLOW_DUPLICATE,
        _with_second(name="oth:loan"),
        _problem(UmlRule.WORKFLOW_DUPLICATE, "lib:loan", "oth:loan", "loan"),
    ),
    WorkflowRow(
        "two diagrams with one workflow IRI",
        UmlRule.WORKFLOW_DUPLICATE,
        _with_second(first=_loan(name="loan"), name="loan"),
        _problem(UmlRule.WORKFLOW_DUPLICATE, "loan"),
    ),
]
