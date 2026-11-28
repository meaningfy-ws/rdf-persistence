"""Slots of associations and dependencies, and what the composition tree owns (R-6, R-8, R-11, R-12; PD-3, PD-8, PD-9, PD-13, PD-15).

An association gives a slot at each end that has a role; a dependency gives one, on its source, ranged
by the enumeration it points at. A slot is owned only when the composition tree names its end
(``UmlAggregates.owned_ends``); the end of an «own graph» composition ranges over ``uri`` and carries
``rp_loaded_graph`` (``loaded_graph_ends``). A composite association is refused (PD-3).
"""

from rdf_persistence_generation.generated.rp_generation import (
    LeftOutReason,
    ReportKind,
    UmlAggregates,
    UmlElement,
    UmlLink,
    UmlLinkEnd,
    UmlLinkKind,
    UmlModel,
    UmlName,
    UmlRule,
)
from rdf_persistence_generation.uml.context import Context, literals_of
from rdf_persistence_generation.uml.naming import slot_name
from rdf_persistence_generation.uml.slots import (
    COMPOSITE,
    LOADED_GRAPH,
    OWNED,
    UNSPECIFIED,
    URI,
    Usage,
    check_bounds,
    described,
    shape_of,
    slot_identity,
)

ASSOCIATION_CLASS = "Class"
DIRECTED = "Source -> Destination"
BIDIRECTIONAL = "Bi-Directional"


Marks = dict[
    tuple[int, int], tuple[str, ...]
]  # (connector, holder) -> the annotations its slot carries


def _marks(aggregates: UmlAggregates) -> Marks:
    """The ends the tree owns and those of an «own graph» composition, each with its annotation (PD-9)."""
    marks: Marks = {(end.link_id, end.holder_id): (OWNED,) for end in aggregates.owned_ends or []}
    for end in aggregates.loaded_graph_ends or []:
        marks[(end.link_id, end.holder_id)] = (LOADED_GRAPH,)
    return marks


def _name_of(ctx: Context, element_id: int) -> str:
    """The local name of a link's end; an end the model lists nowhere is an internal error (D-17).

    Raises:
        LookupError: The end is in neither ``uml_classes`` nor ``uml_outside_classes``.
    """
    element = ctx.elements.get(element_id)
    if element is not None:
        return element.label
    if element_id not in ctx.class_names:
        raise LookupError(
            f"link end {element_id} is in neither uml_classes nor uml_outside_classes"
        )
    return ctx.class_names[element_id]


def _range_of(ctx: Context, end: UmlLinkEnd, holder: UmlElement, slot: str) -> str | None:
    """The range a slot has; None when the target is in an excluded package and the slot is not made."""
    target = ctx.elements.get(end.other_id)
    if target is not None:
        return URI if target.is_enum and not literals_of(target) else target.label
    why = ctx.left_out.get(end.other_id)
    if why == LeftOutReason.NOT_GENERATED:
        return URI
    if why == LeftOutReason.EXCLUDED:
        element = f"{holder.label}.{slot} -> {_name_of(ctx, end.other_id)}"
        ctx.findings.note(
            ReportKind.EXCLUDED_LINK, element, "the target is in an excluded package, so no slot"
        )
        return None
    if why == LeftOutReason.OUTSIDE:
        ctx.findings.note(
            ReportKind.OUTSIDE_LINK,
            f"{holder.label}.{slot}",
            "the target is outside the converted subtree, a URI",
        )
        return URI
    _name_of(ctx, end.other_id)  # a class the model lists but refused has its own problem
    return None


def _enum_holder(ctx: Context, holder: UmlElement, element: str) -> bool:
    """Whether an enumeration holds the slot, which no rule maps: a problem naming the slot."""
    if holder.is_enum:
        ctx.findings.no_rule(element, "a slot held by an enumeration")
    return bool(holder.is_enum)


def _end_name(ctx: Context, end: UmlLinkEnd, holder: UmlElement | None) -> UmlName | None:
    """The resolved role of an end whose holder is generated; None for an end with no role."""
    if holder is None or not end.end_role:
        return None
    return ctx.resolve(end.end_role, _name_of(ctx, end.holder_id))


def _end_usage(ctx: Context, link: UmlLink, end: UmlLinkEnd, marks: Marks) -> Usage | None:
    holder = ctx.elements.get(end.holder_id)
    name = _end_name(ctx, end, holder)
    if holder is None or name is None:
        return None
    element = f"{holder.label}.{name.name}"
    identities = slot_identity(ctx, name, element)
    if identities is None:
        return None
    slot = str(identities[0].name)
    element = f"{holder.label}.{slot}"
    if _enum_holder(ctx, holder, element):
        return None
    bounds = check_bounds(ctx, element, _card_text(ctx, element, end.end_card))
    marked = marks.get((link.connector_id, end.holder_id), ())
    target_range = URI if LOADED_GRAPH in marked else _range_of(ctx, end, holder, slot)
    if bounds is None or target_range is None:
        return None
    described_as = (target_range, described(ctx, element, link.note))
    shape = shape_of(slot, described_as, bounds, marked=marked)
    return Usage(holder, identities, (1, 0, slot), shape)


def _card_text(ctx: Context, element: str, card: str | None) -> str:
    if card is None or not card.strip():
        ctx.findings.note(ReportKind.UNSPECIFIED_MULTIPLICITY, element, f"read as {UNSPECIFIED}")
        return UNSPECIFIED
    return card


def _wrong_direction(link: UmlLink) -> str | None:
    """Why an association's direction is not accepted (D-14), or None when it is.

    ``Source -> Destination`` takes the destination role only; a source role as well asks for
    ``Bi-Directional``, as the model2owl convention does. ``Bi-Directional`` takes both.
    """
    if link.link_kind != UmlLinkKind.ASSOCIATION or link.direction == BIDIRECTIONAL:
        return None
    if link.direction != DIRECTED:
        return f"direction {link.direction}" if link.direction else "no direction"
    if link.source_role:
        return f"direction {DIRECTED} with a source role, which needs {BIDIRECTIONAL}"
    return None


def _refusal(link: UmlLink) -> str | None:
    """Why a connector is refused: a stereotype, an association class, a composite whole or a direction."""
    if link.uml_stereotype:
        return f"connector stereotype {link.uml_stereotype}"
    if link.association_class or link.sub_type == ASSOCIATION_CLASS:
        return "association class"
    if link.target_aggregate == COMPOSITE:
        return "a composite whose whole is the destination"
    return _wrong_direction(link)


def _composite_association(ctx: Context, link: UmlLink) -> bool:
    """A composite association whose whole is the source is refused, naming the two-connector form (PD-3)."""
    if link.link_kind != UmlLinkKind.ASSOCIATION or link.source_aggregate != COMPOSITE:
        return False
    whole, part = _name_of(ctx, link.source_id), _name_of(ctx, link.target_id)
    role = slot_name(link.target_role) if link.target_role else ""
    ctx.findings.problem(
        UmlRule.BOUNDARY_OWNED,
        f"{whole}.{role}".rstrip("."),
        f"a composite association; draw an Aggregation (composition) {whole} -> {part} "
        "beside a plain association",
    )
    return True


def _refused(ctx: Context, link: UmlLink) -> bool:
    """A connector no rule maps (see ``_refusal``), or one with no role at all."""
    if _composite_association(ctx, link):
        return True
    reason = _refusal(link)
    if reason is not None:
        role = slot_name(link.target_role) if link.target_role else ""
        ctx.findings.no_rule(f"{_name_of(ctx, link.source_id)}.{role}".rstrip("."), reason)
    elif not link.source_role and not link.target_role:
        ctx.findings.no_rule(
            f"{_name_of(ctx, link.source_id)} -> {_name_of(ctx, link.target_id)}",
            "link with no role",
        )
    else:
        return False
    return True


def _ends(link: UmlLink) -> list[UmlLinkEnd]:
    forward = UmlLinkEnd(
        holder_id=link.source_id,
        other_id=link.target_id,
        end_role=link.target_role,
        end_card=link.target_card,
    )
    if link.link_kind == UmlLinkKind.DEPENDENCY:
        return [forward]
    backward = UmlLinkEnd(
        holder_id=link.target_id,
        other_id=link.source_id,
        end_role=link.source_role,
        end_card=link.source_card,
    )
    return [forward, backward]


def _dependency_target_ok(ctx: Context, link: UmlLink) -> bool:
    if not link.target_role:
        role = slot_name(link.source_role) if link.source_role else ""
        ctx.findings.no_rule(
            f"{_name_of(ctx, link.source_id)}.{role}".rstrip("."),
            "a dependency with a source role only, it needs a destination role",
        )
        return False
    if ctx.not_generated_enum(link.target_id):
        element = f"{_name_of(ctx, link.source_id)}.{slot_name(link.target_role)}"
        ctx.findings.note(
            ReportKind.NOT_GENERATED,
            f"{element} -> {_name_of(ctx, link.target_id)}",
            "the target is not generated, so no slot (R-30)",
        )
        return False
    target = ctx.elements.get(link.target_id)
    if target is not None and not target.is_enum:
        ctx.findings.no_rule(
            f"{_name_of(ctx, link.source_id)}.{link.target_role}",
            "dependency on a class, not an enumeration",
        )
        return False
    return True


def link_usages(ctx: Context, model: UmlModel, aggregates: UmlAggregates) -> list[Usage]:
    """The slots of every association and dependency, in connector order; the tree says which are owned."""
    marks = _marks(aggregates)
    usages: list[Usage] = []
    for link in sorted(model.uml_links or [], key=lambda each: each.connector_id):
        if link.link_kind == UmlLinkKind.GENERALISATION or _refused(ctx, link):
            continue
        if link.link_kind == UmlLinkKind.DEPENDENCY and not _dependency_target_ok(ctx, link):
            continue
        made = (_end_usage(ctx, link, end, marks) for end in _ends(link))
        usages.extend(usage for usage in made if usage is not None)
    return usages
