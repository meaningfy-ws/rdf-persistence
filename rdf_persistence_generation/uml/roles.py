"""PD-3: a role definition drawn as an Object, read into the toolkit's own ``RoleDefinition``.

An Object whose classifier is the drawn toolkit class ``rp:RoleDefinition`` sets the variables ``role``, ``level``
and ``actions`` in its run state. The values are judged by the library's ``RoleDefinition``, so the levels and the
actions are the toolkit's, never a list here (F-5). What the library's class accepts and the loader refuses, no
action at all, is refused here too, naming the object.
"""

from collections import defaultdict
from collections.abc import Sequence

from pydantic import ValidationError

from rdf_persistence.access.domain.generated.rp_access import RoleDefinition
from rdf_persistence_generation.generated.rp_generation import (
    ReportKind,
    UmlModel,
    UmlObject,
    UmlRule,
)
from rdf_persistence_generation.uml.context import Context
from rdf_persistence_generation.uml.dump import yaml_text

TOOLKIT_CLASS = RoleDefinition.__name__  # how ``ctx.drawn_toolkit`` names the drawn class
VARIABLES = tuple(RoleDefinition.model_fields)  # role, level, actions: the fields are the variables
OPERATOR = "="
ACTION_SEPARATOR = ","
ACTIONS_VARIABLE = "actions"
ROLES_SUFFIX = ".roles.yaml"  # the file is ``<root name>.roles.yaml``


def roles_file_text(entries: Sequence[RoleDefinition]) -> str:
    """PD-6: the entries, in the given order, as the YAML list the library's loader reads."""
    return yaml_text(list(entries))


def role_entries(ctx: Context, model: UmlModel) -> list[RoleDefinition]:
    """The role definitions the model's role Objects draw, sorted by role and level; problems and report lines go to ``ctx``."""
    drawn: dict[tuple[str, str], list[str]] = defaultdict(list)
    entries: list[RoleDefinition] = []
    for each in sorted(model.uml_objects or [], key=lambda o: (o.uml_name, o.object_id)):
        if not _is_role(ctx, each):  # the reader leaves out the objects of excluded packages
            continue
        entry = _entry(ctx, each)
        if entry is not None:
            entries.append(entry)
            drawn[(entry.role, entry.level)].append(each.uml_name)
            ctx.findings.note(ReportKind.ROLE, each.uml_name, _line(entry))
    _check_duplicates(ctx, drawn)
    return sorted(entries, key=lambda e: (e.role, e.level))


def _classifier_of(ctx: Context, drawn: UmlObject) -> int | None:
    """The class that types the Object, or None after a problem (PD-11).

    The classifier, or with none the one class the Object realises; a Realisation to another class
    than the classifier, or to two classes, is a ``role_definition`` problem naming the classes.
    """
    realised = sorted(set(drawn.realised_ids or []), key=lambda each: _label(ctx, each))
    classifier = drawn.classifier_id
    if classifier is None and not realised:
        ctx.findings.no_rule(drawn.uml_name, "Object without a classifier")
        return None
    if len(realised) > 1:
        names = " and ".join(_label(ctx, each) for each in realised)
        _refuse(ctx, drawn, f"realises {names}")
        return None
    if classifier is None:
        return realised[0]
    if realised and realised[0] != classifier:
        _refuse(
            ctx,
            drawn,
            f"realises {_label(ctx, realised[0])} but its classifier is {_label(ctx, classifier)}",
        )
        return None
    return classifier


def _label(ctx: Context, class_id: int) -> str:
    return ctx.class_names.get(class_id, str(class_id))


def _is_role(ctx: Context, drawn: UmlObject) -> bool:
    """Whether the Object is typed by the drawn toolkit role class; any other is a ``no_rule`` problem."""
    classifier = _classifier_of(ctx, drawn)
    if classifier is None:
        return False
    if ctx.drawn_toolkit.get(classifier) != TOOLKIT_CLASS:
        ctx.findings.no_rule(drawn.uml_name, f"Object of {_label(ctx, classifier)}")
        return False
    return True


def _line(entry: RoleDefinition) -> str:
    return f"{entry.role} at {entry.level}: {', '.join(entry.actions)}"


def _entry(ctx: Context, drawn: UmlObject) -> RoleDefinition | None:
    values = _variables(ctx, drawn)
    if values is None:
        return None
    actions = _actions(ctx, drawn, values[ACTIONS_VARIABLE])
    if actions is None:
        return None
    try:
        return RoleDefinition.model_validate(
            {
                **values,
                "role": values["role"].strip(),
                "level": values["level"].strip(),
                ACTIONS_VARIABLE: actions,
            }
        )
    except ValidationError as error:
        for found in error.errors():
            field = ".".join(str(part) for part in found["loc"])
            ctx.findings.problem(
                UmlRule.ROLE_DEFINITION,
                drawn.uml_name,
                f"{field}: {found['msg']} (given {found['input']!r})",
            )
        return None


def _variables(ctx: Context, drawn: UmlObject) -> dict[str, str] | None:
    """The run state as one value for each variable, or None after naming each way it is wrong."""
    wrong: list[str] = []
    if drawn.run_state_rest:
        wrong.append(f"text outside the @VAR blocks: {drawn.run_state_rest!r}")
    values: dict[str, str] = {}
    for each in drawn.run_values or []:
        found = _problem_of(each.variable, each.value, each.operator, values)
        if found is None:
            values[str(each.variable)] = str(each.value)
        else:
            wrong.append(found)
            values.setdefault(str(each.variable), "")  # named, so not also reported missing
    wrong.extend(f"variable {name} is missing" for name in VARIABLES if name not in values)
    for text in wrong:
        ctx.findings.problem(UmlRule.ROLE_RUN_STATE, drawn.uml_name, text)
    return None if wrong else values


def _problem_of(
    variable: str | None, value: str | None, operator: str | None, given: dict[str, str]
) -> str | None:
    if variable is None or value is None:
        return f"a run-state block has no {'Variable' if variable is None else 'Value'}" + (
            f" (variable {variable})" if variable else ""
        )
    if variable not in VARIABLES:
        return f"unknown variable {variable}; the variables are {', '.join(VARIABLES)}"
    if operator != OPERATOR:
        return f"variable {variable}: Op {operator!r} is not {OPERATOR!r}"
    if variable in given:
        return f"variable {variable} is given twice"
    return None


def _actions(ctx: Context, drawn: UmlObject, written: str) -> list[str] | None:
    """The comma-separated actions, stripped, empties dropped, in order; none left or a repeat is a problem."""
    actions = [part.strip() for part in written.split(ACTION_SEPARATOR) if part.strip()]
    repeated = sorted({action for action in actions if actions.count(action) > 1})
    if not actions:
        _refuse(ctx, drawn, f"{ACTIONS_VARIABLE}: none left in {written!r}")
    elif repeated:
        _refuse(ctx, drawn, f"{ACTIONS_VARIABLE}: {', '.join(repeated)} given more than once")
    return None if not actions or repeated else actions


def _refuse(ctx: Context, drawn: UmlObject, message: str) -> None:
    ctx.findings.problem(UmlRule.ROLE_DEFINITION, drawn.uml_name, message)


def _check_duplicates(ctx: Context, drawn: dict[tuple[str, str], list[str]]) -> None:
    for (role, level), found in sorted(drawn.items()):
        names = sorted(found)
        if len(names) > 1:
            ctx.findings.problem(
                UmlRule.ROLE_DUPLICATE,
                names[0],
                f"{role} at {level} is also defined by {', '.join(names[1:])}",
            )
