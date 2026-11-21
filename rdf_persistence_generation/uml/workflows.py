"""PD-5: a Statechart diagram read as a workflow, validated by the toolkit's own ``Workflow``.

A diagram names the workflow (a CURIE gives its IRI, a plain name derives one), its State nodes are the states,
the one flow leaving the Initial node names the initial state, and every other flow is a transition tagged with
``roles`` and, optionally, ``comment_required``. The patterns of the names are the library's (F-5), never a copy.
"""

from collections import defaultdict
from collections.abc import Callable, Collection

from pydantic import ValidationError

from rdf_persistence.collaboration.domain.generated.rp_workflow import Workflow, WorkflowTransition
from rdf_persistence_generation.generated.rp_generation import (
    ReportKind,
    UmlModel,
    UmlRule,
    UmlStatechart,
    UmlStateFlow,
    UmlStateNode,
    UmlStateNodeKind,
)
from rdf_persistence_generation.uml.context import Context
from rdf_persistence_generation.uml.dump import yaml_text

WORKFLOWS_FOLDER = "workflows/"
WORKFLOWS_SUFFIX = ".workflow.yaml"  # the file is ``workflows/<workflow name>.workflow.yaml``
ROLES_TAG = "roles"
COMMENT_TAG = "comment_required"
WORKFLOW_TAG = "workflow"  # the class tag that names a workflow
ROLE_SEPARATOR = ","
COMMENT_VALUES = {"true": True, "false": False}

Nodes = dict[int, UmlStateNode]
Placement = dict[int, list[UmlStatechart]]


def workflow_file_text(entry: Workflow) -> str:
    """PD-6: the workflow in the key order of the library's fixture, ``comment_required`` only when true."""
    return yaml_text(entry)


def workflow_files(entries: Collection[Workflow]) -> dict[str, str]:
    """PD-8: each workflow's file, a path relative to ``--out`` to its text."""
    return {
        f"{WORKFLOWS_FOLDER}{each.workflow_name}{WORKFLOWS_SUFFIX}": workflow_file_text(each)
        for each in entries
    }


class Drawn:
    """A Statechart diagram with the workflow name and IRI its drawn name stands for."""

    def __init__(self, chart: UmlStatechart, name: str, iri: str) -> None:
        self.chart = chart
        self.drawn = chart.uml_name
        self.name = name
        self.iri = iri


def workflow_entries(ctx: Context, model: UmlModel, roles: Collection[str]) -> list[Workflow]:
    """The workflows the model's Statechart diagrams draw, sorted by name; problems and report lines go to ``ctx``.

    ``roles`` are the role names the model draws as role definitions: a transition may name no other (DEC-5).
    """
    nodes = _usable(ctx, model)
    charts = model.uml_statecharts or []
    on = _placement(ctx, nodes, charts)
    drawn = _resolved(ctx, [c for c in charts if _placed_once(c, nodes, on)])
    _check_duplicates(ctx, drawn)
    flows = _assigned(ctx, model.uml_state_flows or [], nodes, on)
    built = _built(ctx, drawn, nodes, flows, roles)
    _check_classes(
        ctx, charts, {each.name for each in drawn}, {n: d for n, (d, _) in built.items()}
    )
    return sorted((found for _, found in built.values()), key=lambda each: each.workflow_name)


def _placed_once(chart: UmlStatechart, nodes: Nodes, on: Placement) -> bool:
    """Whether every usable node of the diagram is on this diagram alone; else it is not judged further."""
    return all(len(on[each]) == 1 for each in chart.node_ids or [] if each in nodes)


def _built(
    ctx: Context,
    drawn: list[Drawn],
    nodes: Nodes,
    flows: dict[int, list[UmlStateFlow]],
    roles: Collection[str],
) -> dict[str, tuple[Drawn, Workflow]]:
    """The workflow of each diagram that has one, by workflow name, each with its report line."""
    built: dict[str, tuple[Drawn, Workflow]] = {}
    for each in drawn:
        found = _workflow(ctx, each, nodes, flows[each.chart.diagram_id], roles)
        if found is not None:
            built[each.name] = (each, found)
            ctx.findings.note(ReportKind.WORKFLOW, each.drawn, _counts(found))
    return built


def _counts(found: Workflow) -> str:
    return (
        f"{len(found.workflow_states)} states, {len(found.workflow_transitions or [])} transitions"
    )


def _usable(ctx: Context, model: UmlModel) -> Nodes:
    """The state nodes a workflow can hold; a node that is neither a State nor Initial is ``no_rule`` (D-5)."""
    nodes: Nodes = {}
    for each in model.uml_state_nodes or []:
        if each.node_kind is None:
            ctx.findings.no_rule(each.uml_name, f"StateNode kind {each.node_type}")
        else:
            nodes[each.object_id] = each
    return nodes


def _placement(ctx: Context, nodes: Nodes, charts: list[UmlStatechart]) -> Placement:
    """The diagrams each usable node is placed on; a node on none, or on two, is a problem naming it."""
    on: Placement = defaultdict(list)
    for chart in charts:
        for node_id in chart.node_ids or []:
            if node_id in nodes:
                on[node_id].append(chart)
    for node_id, node in sorted(nodes.items()):
        why = _placement_problem(sorted(chart.uml_name for chart in on[node_id]))
        if why is not None:
            ctx.findings.problem(UmlRule.WORKFLOW_NODE, node.uml_name, why)
    return on


def _placement_problem(names: list[str]) -> str | None:
    if not names:
        return "is on no Statechart diagram"
    return f"is on the diagrams {', '.join(names)}" if len(names) > 1 else None


def _resolved(ctx: Context, charts: list[UmlStatechart]) -> list[Drawn]:
    """Each diagram with its workflow name and IRI; a plain name derives the IRI (DEC-4), an unknown prefix is skipped."""
    drawn = []
    for chart in sorted(charts, key=lambda each: (each.uml_name, each.diagram_id)):
        name = ctx.resolve(chart.uml_name, chart.uml_name)
        if name is None:
            continue
        iri = name.iri or f"{ctx.settings.schema_base}{WORKFLOWS_FOLDER}{name.name}"
        if name.iri is None:
            message = f"the IRI {iri} is derived from the diagram name"
            ctx.findings.note(ReportKind.DERIVED_IRI, chart.uml_name, message)
        drawn.append(Drawn(chart, name.name, iri))
    return drawn


def _check_duplicates(ctx: Context, drawn: list[Drawn]) -> None:
    """Two diagrams with one workflow name, or else one IRI, are a problem naming both."""
    by_name = _repeated(drawn, lambda each: each.name)
    reported = {each.drawn for group in by_name.values() for each in group}
    groups = {f"name {value}": group for value, group in by_name.items()}
    for value, group in _repeated(drawn, lambda each: each.iri).items():
        if not {each.drawn for each in group} <= reported:  # not already reported as one name
            groups[f"IRI {value}"] = group
    for what, group in sorted(groups.items()):
        others = ", ".join(each.drawn for each in group[1:])
        message = f"workflow {what} is also drawn by {others}"
        ctx.findings.problem(UmlRule.WORKFLOW_DUPLICATE, group[0].drawn, message)


def _repeated(drawn: list[Drawn], key: Callable[[Drawn], str]) -> dict[str, list[Drawn]]:
    """The diagrams that share a value of ``key``, by that value; the ones alone are left out."""
    groups: dict[str, list[Drawn]] = defaultdict(list)
    for each in drawn:
        groups[key(each)].append(each)
    return {value: group for value, group in groups.items() if len(group) > 1}


def _label(nodes: Nodes, flow: UmlStateFlow) -> str:
    return f"{nodes[flow.source_id].uml_name} -> {nodes[flow.target_id].uml_name}"


def _assigned(
    ctx: Context, flows: list[UmlStateFlow], nodes: Nodes, on: Placement
) -> dict[int, list[UmlStateFlow]]:
    """The flows of each diagram; a flow between two diagrams is a problem naming it."""
    assigned: dict[int, list[UmlStateFlow]] = defaultdict(list)
    for flow in flows:
        if flow.source_id not in nodes or flow.target_id not in nodes:
            continue
        start, end = on[flow.source_id], on[flow.target_id]
        if len(start) != 1 or len(end) != 1:
            continue  # a node on no diagram or two is already a problem
        if start[0].diagram_id == end[0].diagram_id:
            assigned[start[0].diagram_id].append(flow)
        else:
            message = f"runs between the diagrams {start[0].uml_name} and {end[0].uml_name}"
            ctx.findings.problem(UmlRule.WORKFLOW_TRANSITION, _label(nodes, flow), message)
    return assigned


def _workflow(
    ctx: Context, drawn: Drawn, nodes: Nodes, flows: list[UmlStateFlow], roles: Collection[str]
) -> Workflow | None:
    """The workflow of one diagram, or None after naming each way it is wrong (PD-5 steps 3 to 6)."""
    chart_nodes = [nodes[each] for each in drawn.chart.node_ids or [] if each in nodes]
    start = _initial(ctx, drawn, nodes, chart_nodes, flows)
    if start is None:
        return None
    first, initial_state = start
    states = _states(ctx, drawn, chart_nodes)
    transitions = _transitions(ctx, nodes, [each for each in flows if each is not first], roles)
    if transitions is None or states is None:
        return None
    return _validated(ctx, drawn, states, initial_state, transitions)


def _states(ctx: Context, drawn: Drawn, chart_nodes: list[UmlStateNode]) -> list[str] | None:
    """The State names as drawn, sorted; None after naming each one drawn twice."""
    states = sorted(
        each.uml_name for each in chart_nodes if each.node_kind == UmlStateNodeKind.STATE
    )
    twice = sorted({name for name in states if states.count(name) > 1})
    for name in twice:
        ctx.findings.problem(
            UmlRule.WORKFLOW_DEFINITION, drawn.drawn, f"state {name} is drawn twice"
        )
    return None if twice else states


def _initial(
    ctx: Context,
    drawn: Drawn,
    nodes: Nodes,
    chart_nodes: list[UmlStateNode],
    flows: list[UmlStateFlow],
) -> tuple[UmlStateFlow, str] | None:
    """The flow that leaves the Initial node and the state it names; None after a problem."""
    starts = [each for each in chart_nodes if each.node_kind == UmlStateNodeKind.INITIAL]
    if len(starts) != 1:
        message = f"{len(starts)} Initial nodes, expected one"
        ctx.findings.problem(UmlRule.WORKFLOW_INITIAL, drawn.drawn, message)
        return None
    leaving = [each for each in flows if each.source_id == starts[0].object_id]
    if len(leaving) != 1:
        message = f"{len(leaving)} flows leave the Initial node, expected one"
        ctx.findings.problem(UmlRule.WORKFLOW_INITIAL, drawn.drawn, message)
        return None
    flow, target = leaving[0], nodes[leaving[0].target_id]
    why = _start_problem(flow, target)
    if why is not None:
        ctx.findings.problem(UmlRule.WORKFLOW_INITIAL, _label(nodes, flow), why)
        return None
    return flow, target.uml_name


def _start_problem(flow: UmlStateFlow, target: UmlStateNode) -> str | None:
    """What is wrong with the flow from the Initial node: it carries tags, or does not lead to a state."""
    if flow.uml_tagged_values:
        return "the flow from the Initial node carries tagged values"
    if target.node_kind != UmlStateNodeKind.STATE:
        return "the flow from the Initial node does not lead to a state"
    return None


def _transitions(
    ctx: Context, nodes: Nodes, flows: list[UmlStateFlow], roles: Collection[str]
) -> list[WorkflowTransition] | None:
    """The transitions sorted by source and target; None after a problem."""
    found: dict[tuple[str, str], WorkflowTransition] = {}
    failed = False
    for flow in flows:
        entry = _transition(ctx, nodes, flow, roles)
        key = (nodes[flow.source_id].uml_name, nodes[flow.target_id].uml_name)
        if entry is None:
            failed = True
        elif key in found:
            ctx.findings.problem(UmlRule.WORKFLOW_TRANSITION, _label(nodes, flow), "is drawn twice")
            failed = True
        else:
            found[key] = entry
    return None if failed else [found[key] for key in sorted(found)]


def _transition(
    ctx: Context, nodes: Nodes, flow: UmlStateFlow, roles: Collection[str]
) -> WorkflowTransition | None:
    label = _label(nodes, flow)
    why = _transition_problem(nodes, flow, roles)
    if isinstance(why, str):
        ctx.findings.problem(UmlRule.WORKFLOW_TRANSITION, label, why)
        return None
    named, comment = why
    return WorkflowTransition(
        from_state=nodes[flow.source_id].uml_name,
        to_state=nodes[flow.target_id].uml_name,
        transition_roles=named,
        comment_required=comment,
    )


def _transition_problem(
    nodes: Nodes, flow: UmlStateFlow, roles: Collection[str]
) -> str | tuple[list[str], bool]:
    """What is wrong with a transition, else its roles and whether it needs a comment."""
    if nodes[flow.target_id].node_kind == UmlStateNodeKind.INITIAL:
        return "leads into the Initial node"
    tags = _tags_of(flow)
    if isinstance(tags, str):
        return tags
    named = _roles_of(tags.get(ROLES_TAG, ""), roles)
    comment = tags.get(COMMENT_TAG, "false")
    if isinstance(named, str):
        return named
    if comment not in COMMENT_VALUES:
        return f"{COMMENT_TAG}: {comment!r} is not true or false"
    return named, COMMENT_VALUES[comment]


def _tags_of(flow: UmlStateFlow) -> dict[str, str] | str:
    """The tagged values of a transition by name, or what is wrong with them: one twice, or another than ours."""
    given = flow.uml_tagged_values or []
    tags = {each.name: (each.tag_value or "").strip() for each in given}
    other = sorted(set(tags) - {ROLES_TAG, COMMENT_TAG})
    if len(tags) != len(given):
        return "a tagged value is given twice"
    if other:
        return f"tagged value {', '.join(other)} is not {ROLES_TAG} or {COMMENT_TAG}"
    return tags


def _roles_of(written: str, roles: Collection[str]) -> list[str] | str:
    """The roles a ``roles`` tag names, or what is wrong with it: none, or one no role definition draws."""
    named = [each.strip() for each in written.split(ROLE_SEPARATOR) if each.strip()]
    unknown = sorted(set(named) - set(roles))
    if not named:
        return f"{ROLES_TAG}: none given in {written!r}"
    if unknown:
        return f"{ROLES_TAG}: {', '.join(unknown)} is not drawn as a role definition"
    return named


def _validated(
    ctx: Context,
    drawn: Drawn,
    states: list[str],
    initial_state: str,
    transitions: list[WorkflowTransition],
) -> Workflow | None:
    try:
        return Workflow(
            id=drawn.iri,
            workflow_name=drawn.name,
            workflow_states=states,
            initial_state=initial_state,
            workflow_transitions=transitions,
        )
    except ValidationError as error:
        for found in error.errors():
            field = ".".join(str(part) for part in found["loc"])
            message = f"{field}: {found['msg']} (given {found['input']!r})"
            ctx.findings.problem(UmlRule.WORKFLOW_DEFINITION, drawn.drawn, message)
        return None


def _check_classes(
    ctx: Context, charts: list[UmlStatechart], names: set[str], built: dict[str, Drawn]
) -> None:
    """With a Statechart converted, a class's ``workflow`` tag names a drawn workflow; a workflow no class names is reported."""
    if not charts:
        return
    named: set[str] = set()
    for element in sorted(ctx.elements.values(), key=lambda each: each.label):
        written = ctx.tags.get(element.uml_class.object_id, {}).get(WORKFLOW_TAG)
        if written is None:
            continue
        named.add(written)
        if written not in names:
            message = f"{WORKFLOW_TAG}: {written!r} is drawn by no Statechart diagram"
            ctx.findings.problem(UmlRule.WORKFLOW_CLASS, element.label, message)
    for name, each in sorted(built.items()):
        if name not in named:
            ctx.findings.note(ReportKind.WORKFLOW, each.drawn, "named by no class")
