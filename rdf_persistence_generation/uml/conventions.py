"""The conventions the converter reports but never refuses, as pure passes (PD-13, PD-15, PD-19, PD-20).

A convention line is no problem: a normal run writes with it and ``--check`` fails on it. Every pass
here takes records (and ``Usage``) and returns report lines; none reads or fills a ``Context``
(pinned by ``test_uml_pass_signatures``). ``missing_notes`` is the one home of ``no-note`` (PD-20);
``convention_lines`` holds the rest: diagrams, boundaries, names, enumerations, toolkit parents and
the tenant's required pointers.
"""

from collections.abc import Mapping
from typing import Final

from rdf_persistence_generation.generated.rp_generation import (
    ReportKind,
    ReportLine,
    UmlAggregates,
    UmlComposition,
    UmlDiagram,
    UmlElement,
    UmlLink,
    UmlLinkKind,
    UmlModel,
    UmlRule,
)
from rdf_persistence_generation.uml.aggregates import BIDIRECTIONAL
from rdf_persistence_generation.uml.classes import description_of
from rdf_persistence_generation.uml.context import local_of
from rdf_persistence_generation.uml.naming import CURIE_SEPARATOR, check_local_name
from rdf_persistence_generation.uml.qea import ENUMERATION_TYPE, STATECHART_TYPE
from rdf_persistence_generation.uml.roles import TOOLKIT_CLASS
from rdf_persistence_generation.uml.slots import FROM_ATTRIBUTE, Usage, is_owned

# The report kinds whose lines fail ``--check``: exactly the eleven of PD-13. ``deprecated_root`` and
# ``toolkit_slot_kept`` are informational, so a model that still draws an agreeing «root», or follows
# the reference-collection pattern, passes.
NO_NOTE: Final = (
    ReportKind.NO_NOTE
)  # named once, so this module is the one home of the kind (PD-20)
CONVENTION_KINDS: Final = frozenset(
    {
        ReportKind.BOUNDARY_DISAGREES,
        ReportKind.COMPOSITION_NAMED,
        ReportKind.AGGREGATES_DIAGRAM,
        ReportKind.COMPOSITION_DIAGRAM,
        ReportKind.UNPREFIXED_NAME,
        ReportKind.UNUSED_ENUMERATION,
        ReportKind.DRAWN_TOOLKIT_PARENT,
        ReportKind.TENANT_REQUIRED_POINTER,
        NO_NOTE,
        ReportKind.UNSPECIFIED_MULTIPLICITY,
        ReportKind.IMPLICIT_MEANING,
    }
)
NO_NOTE_TEXT: Final = "no note, so no description"
AGGREGATES_SUFFIX: Final = " · aggregates"  # U+00B7 between two spaces (PD-12)
BOUNDARY_PREFIX: Final = "Aggregate:"
ARROW: Final = "→"


def _line(kind: ReportKind, element: str, message: str) -> ReportLine:
    return ReportLine(report_kind=kind, element=element, message=message)


def _noteless_literals(element: UmlElement) -> list[str]:
    """The literals of an enumeration that have a valid local name and no note."""
    found: list[str] = []
    for literal in element.uml_class.uml_attributes or []:
        name = f"{element.label}.{local_of(literal.name)}"
        valid = check_local_name(local_of(literal.name), name, UmlRule.CLASS_IRI) is None
        if valid and description_of(literal.note) is None:
            found.append(name)
    return found


def _usage_element(usage: Usage) -> str:
    """How a slot is named in a line: an attribute by its written local name, a role by its slot name."""
    if usage.order[0] == FROM_ATTRIBUTE:
        return f"{usage.holder.label}.{usage.written.name}"
    return f"{usage.holder.label}.{usage.name}"


def missing_notes(
    elements: list[UmlElement], usages: list[Usage], toolkit_usages: list[Usage]
) -> list[ReportLine]:
    """One ``no-note`` line for each class, enumeration, literal, attribute and role with no note (PD-20).

    Args:
        elements: The classes and enumerations the conversion generates.
        usages: The slots that stay domain slots; a slot with no description has no note.
        toolkit_usages: The slots the toolkit takes over (PD-18); they were noted before, so they still are.

    Returns:
        The lines, each naming its element as the report always did; a role object, a state and a
        transition are no element here and are never named.
    """
    names = [
        element.label for element in elements if description_of(element.uml_class.note) is None
    ]
    names += [
        name for element in elements if element.is_enum for name in _noteless_literals(element)
    ]
    names += [
        _usage_element(usage)
        for usage in [*usages, *toolkit_usages]
        if usage.shape.description is None
    ]
    return [_line(NO_NOTE, name, NO_NOTE_TEXT) for name in dict.fromkeys(names)]


def _other_members(model: UmlModel) -> dict[int, str]:
    """The objects and the states of a model by id, as a line names them."""
    named = {each.object_id: f"object {each.uml_name}" for each in model.uml_objects or []}
    named.update({each.object_id: f"state {each.uml_name}" for each in model.uml_state_nodes or []})
    return named


class _Drawing:
    """The names of what a model draws, by id: classes, enumerations, objects and states (a lookup, no state)."""

    def __init__(self, model: UmlModel, elements: list[UmlElement]) -> None:
        self.classes = {
            each.object_id: each
            for each in [*(model.uml_classes or []), *(model.uml_outside_classes or [])]
        }
        self.labels = {key: local_of(each.name) for key, each in self.classes.items()}
        self.labels.update({each.uml_class.object_id: each.label for each in elements})
        self.others = _other_members(model)
        self.boundaries = {each.object_id for each in model.uml_boundaries or []}

    def name(self, object_id: int) -> str:
        return self.labels.get(object_id, str(object_id))

    def odd_one(self, object_id: int) -> str | None:
        """What a member is when it is no class, note, text or boundary (PD-12), else None."""
        found = self.classes.get(object_id)
        if object_id in self.boundaries or (
            found is not None and found.object_type != ENUMERATION_TYPE
        ):
            return None
        if found is not None:
            return f"enumeration {self.name(object_id)}"
        return self.others.get(object_id, f"element {object_id}")

    def link_text(self, each: UmlLink) -> str:
        """A connector as a line names it: its kind and the slot it gives, or its two ends."""
        role = each.target_role or each.source_role
        holder = each.source_id if each.target_role else each.target_id
        ends = f"{self.name(each.source_id)} -> {self.name(each.target_id)}"
        named = f"{self.name(holder)}.{local_of(role)}" if role else ends
        return f"{UmlLinkKind(each.link_kind).value} {named}"

    def composition_text(self, each: UmlComposition) -> str:
        return f"composition {self.name(each.whole_id)} {ARROW} {self.name(each.part_id)}"


def _shown(diagram: UmlDiagram, connector_id: int, ends: tuple[int, int]) -> bool:
    """EA's display rule (RISK-6): both ends are on the diagram and no row hides the connector."""
    members = set(diagram.element_ids or [])
    return set(ends) <= members and connector_id not in (diagram.hidden_connector_ids or [])


def _is_aggregates(diagram: UmlDiagram) -> bool:
    return diagram.name.endswith(AGGREGATES_SUFFIX)


def _aggregates_lines(
    model: UmlModel, drawing: _Drawing, diagram: UmlDiagram, package: str
) -> list[ReportLine]:
    """What an aggregates diagram may not show: an element that is no class, an association, a wrong name."""
    found = _odd_members(drawing, diagram) + _shown_associations(model, drawing, diagram)
    prefix = diagram.name.removesuffix(AGGREGATES_SUFFIX)
    if prefix != package:
        found.append(f"starts with {prefix}, not the package name {package}")
    return [_line(ReportKind.AGGREGATES_DIAGRAM, diagram.name, message) for message in found]


def _odd_members(drawing: _Drawing, diagram: UmlDiagram) -> list[str]:
    """What the diagram shows that is no class, note, text or boundary, named."""
    odd = (drawing.odd_one(each) for each in sorted(diagram.element_ids or []))
    return [f"shows the {text}" for text in odd if text is not None]


def _shown_associations(model: UmlModel, drawing: _Drawing, diagram: UmlDiagram) -> list[str]:
    """The associations and dependencies the diagram shows: both ends on it and no row hiding them."""
    return [
        f"shows the {drawing.link_text(each)}"
        for each in sorted(model.uml_links or [], key=lambda link: link.connector_id)
        if each.link_kind != UmlLinkKind.GENERALISATION
        and _shown(diagram, each.connector_id, (each.source_id, each.target_id))
    ]


def _composition_lines(model: UmlModel, drawing: _Drawing, diagram: UmlDiagram) -> list[ReportLine]:
    """A diagram that is no aggregates diagram shows no composition: it belongs on the aggregates one."""
    return [
        _line(
            ReportKind.COMPOSITION_DIAGRAM,
            diagram.name,
            f"shows the {drawing.composition_text(each)}",
        )
        for each in sorted(model.uml_compositions or [], key=lambda each: each.composition_id)
        if _shown(diagram, each.composition_id, (each.whole_id, each.part_id))
    ]


def _diagram_lines(model: UmlModel, elements: list[UmlElement]) -> list[ReportLine]:
    """The lines of the class diagrams of the converted packages (PD-12); a Statechart is read apart."""
    drawing = _Drawing(model, elements)
    packages = {each.package_id: each.name for each in model.uml_packages or []}
    found: list[ReportLine] = []
    for diagram in model.uml_diagrams or []:
        package = packages.get(diagram.package_id or -1)
        if package is None or diagram.diagram_type == STATECHART_TYPE:
            continue
        if _is_aggregates(diagram):
            found += _aggregates_lines(model, drawing, diagram, package)
        else:
            found += _composition_lines(model, drawing, diagram)
    return found


def _boundary_subject(name: str) -> str:
    """The class a boundary is named for: its name after an optional leading ``Aggregate:``."""
    text = name.strip()
    return text.removeprefix(BOUNDARY_PREFIX).strip() if text.startswith(BOUNDARY_PREFIX) else text


def _boundary_lines(
    model: UmlModel, elements: list[UmlElement], aggregates: UmlAggregates
) -> list[ReportLine]:
    """A boundary of a converted package that names no derived root or the tenant root (PD-7, D-1)."""
    written = _root_names(elements, aggregates)
    packages = {each.package_id for each in model.uml_packages or []}
    return [
        _line(
            ReportKind.BOUNDARY_DISAGREES,
            each.name,
            "names no root; a boundary is an annotation",
        )
        for each in sorted(model.uml_boundaries or [], key=lambda found: found.object_id)
        if each.package_id in packages and _boundary_subject(each.name) not in written
    ]


def _root_names(elements: list[UmlElement], aggregates: UmlAggregates) -> set[str]:
    """The names a derived root or the tenant root goes by: its label and its written name."""
    tops = {*(aggregates.root_ids or []), aggregates.tenant_root_id}
    held = [each for each in elements if each.uml_class.object_id in tops]
    return {each.label for each in held} | {each.uml_class.name for each in held}


def _unprefixed(written: str) -> bool:
    return CURIE_SEPARATOR not in written


def _role_holders(each: UmlLink) -> list[tuple[int, str | None]]:
    """The holder and written role of each end of an association or dependency that may give a slot."""
    ends: list[tuple[int, str | None]] = [(each.source_id, each.target_role)]
    if each.link_kind == UmlLinkKind.ASSOCIATION and each.direction == BIDIRECTIONAL:
        ends.append((each.target_id, each.source_role))
    return ends


def _unprefixed_lines(model: UmlModel, elements: list[UmlElement]) -> list[ReportLine]:
    """A class, an attribute or a role written with no prefix; an enumeration literal has its own line (C-1)."""
    held = {each.uml_class.object_id: each for each in elements if not each.is_enum}
    names = [each.label for each in held.values() if _unprefixed(each.uml_class.name)]
    names += _unprefixed_attributes(list(held.values()))
    names += _unprefixed_roles(model, held)
    return [_line(ReportKind.UNPREFIXED_NAME, name, "no prefix") for name in dict.fromkeys(names)]


def _unprefixed_attributes(held: list[UmlElement]) -> list[str]:
    return [
        f"{each.label}.{attribute.name}"
        for each in held
        for attribute in each.uml_class.uml_attributes or []
        if _unprefixed(attribute.name)
    ]


def _unprefixed_roles(model: UmlModel, held: Mapping[int, UmlElement]) -> list[str]:
    slot_links = [
        each for each in model.uml_links or [] if each.link_kind != UmlLinkKind.GENERALISATION
    ]
    ends = [end for each in slot_links for end in _role_holders(each)]
    return [
        f"{held[holder].label}.{role}"
        for holder, role in ends
        if holder in held and role and _unprefixed(role)
    ]


def _unused_enumeration_lines(elements: list[UmlElement], usages: list[Usage]) -> list[ReportLine]:
    """An enumeration no slot ranges over (C-5): it is generated all the same."""
    used = {str(each.shape.range) for each in usages}
    return [
        _line(ReportKind.UNUSED_ENUMERATION, each.label, "used by no dependency")
        for each in elements
        if each.is_enum and each.label not in used
    ]


def _generalisations(model: UmlModel) -> list[UmlLink]:
    found = [each for each in model.uml_links or [] if each.link_kind == UmlLinkKind.GENERALISATION]
    return sorted(found, key=lambda link: link.connector_id)


def _reported_parents(
    drawn_toolkit: Mapping[int, str], classifiers: set[int | None]
) -> dict[int, str]:
    """The drawn toolkit classes a child should name by a tag; a role definition that types Objects is not one."""
    return {
        key: name
        for key, name in drawn_toolkit.items()
        if not (name == TOOLKIT_CLASS and key in classifiers)
    }


def _toolkit_parent_lines(
    model: UmlModel, elements: list[UmlElement], drawn_toolkit: Mapping[int, str]
) -> list[ReportLine]:
    """A generalisation to a drawn toolkit class, which ``rp_mixins`` says as well (C-11, R-28).

    A drawn ``RoleDefinition`` that classifies Objects is the roles file's type, not a parent.
    """
    held = {each.uml_class.object_id: each for each in elements}
    classifiers = {each.classifier_id for each in model.uml_objects or []}
    parents = _reported_parents(drawn_toolkit, classifiers)
    generalisations = _generalisations(model)
    return [
        _line(
            ReportKind.DRAWN_TOOLKIT_PARENT,
            held[each.source_id].label,
            f"prefer rp_mixins={parents[each.target_id]}",
        )
        for each in generalisations
        if each.source_id in held and each.target_id in parents
    ]


def _tenant_aggregate(aggregates: UmlAggregates) -> set[int]:
    """The tenant root and the classes it reaches; empty when the model has no tenant root."""
    tenant = aggregates.tenant_root_id
    if tenant is None:
        return set()
    reached = {
        row.part_id for row in aggregates.reached_from or [] if tenant in (row.top_ids or [])
    }
    return {tenant, *reached}


def _tenant_pointer_lines(
    elements: list[UmlElement], aggregates: UmlAggregates, usages: list[Usage]
) -> list[ReportLine]:
    """A required pointer from the tenant's aggregate to a class outside it (C-12, D-3)."""
    inside = _tenant_aggregate(aggregates)
    by_label = {each.label: each for each in elements if not each.is_enum}
    found: list[ReportLine] = []
    for usage in usages:
        target = by_label.get(str(usage.shape.range))
        if (
            usage.holder.uml_class.object_id in inside
            and usage.shape.required
            and not is_owned(usage.shape)
            and target is not None
            and target.uml_class.object_id not in inside
        ):
            found.append(
                _line(
                    ReportKind.TENANT_REQUIRED_POINTER,
                    f"{usage.holder.label}.{usage.name}",
                    "required, cannot be set when the tenant is created",
                )
            )
    return found


def convention_lines(
    model: UmlModel,
    elements: list[UmlElement],
    aggregates: UmlAggregates,
    usages: list[Usage],
    drawn_toolkit: Mapping[int, str],
) -> list[ReportLine]:
    """The convention lines a model earns besides ``no-note`` (PD-13, PD-15, D-1, D-3), sorted.

    Args:
        model: What the reader took from the file: the packages, links, compositions, boundaries,
            objects and diagrams.
        elements: The classes and enumerations the conversion generates.
        aggregates: The result of ``derive_aggregates``: the roots, the tenant root, the reach.
        usages: Every slot of the run, the toolkit's included (an enumeration a toolkit slot uses is used).
        drawn_toolkit: The toolkit classes the model draws, by id (R-28); not an element.

    Returns:
        The ``aggregates-diagram``, ``composition-diagram``, ``boundary-disagrees``, ``unprefixed-name``,
        ``unused-enumeration``, ``drawn-toolkit-parent`` and ``tenant-required-pointer`` lines.
    """
    found = [
        *_diagram_lines(model, elements),
        *_boundary_lines(model, elements, aggregates),
        *_unprefixed_lines(model, elements),
        *_unused_enumeration_lines(elements, usages),
        *_toolkit_parent_lines(model, elements, drawn_toolkit),
        *_tenant_pointer_lines(elements, aggregates, usages),
    ]
    return sorted(
        found,
        key=lambda each: (str(ReportKind(each.report_kind).value), each.element, each.message),
    )
