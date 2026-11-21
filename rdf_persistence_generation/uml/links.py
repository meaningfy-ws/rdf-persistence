"""Slots of associations and dependencies, and what a boundary owns (R-6, R-8, R-11, R-12; PD-8, PD-13, PD-15).

An association gives a slot at each end that has a role; a dependency gives one, on its source, ranged
by the enumeration it points at. A slot from a member of a boundary to another member than its root is
owned (and so is the destination of a composite association).
"""

from rdf_persistence_generation.generated.rp_generation import (
    ReportKind,
    UmlBoundary,
    UmlElement,
    UmlLink,
    UmlLinkEnd,
    UmlLinkKind,
    UmlModel,
    UmlName,
)
from rdf_persistence_generation.uml.context import (
    LEFT_EXCLUDED,
    LEFT_NOT_GENERATED,
    LEFT_OUTSIDE,
    Context,
    is_boundary_root,
    literals_of,
)
from rdf_persistence_generation.uml.naming import slot_name
from rdf_persistence_generation.uml.slots import (
    COMPOSITE,
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


def _boundary_pairs(ctx: Context, boundary: UmlBoundary) -> set[tuple[int, int]]:
    """The owned pairs of one boundary: from each member to each member but its root."""
    members = [m for m in boundary.member_ids or [] if m in ctx.elements]
    roots = [m for m in members if is_boundary_root(ctx.elements[m])]
    if len(roots) != 1:
        ctx.findings.no_rule(
            boundary.name, f"a boundary needs exactly one root, this one has {len(roots)}"
        )
        return set()
    return {(m, p) for m in members for p in members if p != roots[0]}


def owned_pairs(ctx: Context, model: UmlModel) -> set[tuple[int, int]]:
    """The (holder, target) pairs a boundary makes owned; a boundary without exactly one root is a problem."""
    pairs: set[tuple[int, int]] = set()
    for each in sorted(model.uml_boundaries or [], key=lambda b: (b.name, b.object_id)):
        pairs |= _boundary_pairs(ctx, each)
    return pairs


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
    if why == LEFT_NOT_GENERATED:
        return URI
    if why == LEFT_EXCLUDED:
        element = f"{holder.label}.{slot} -> {_name_of(ctx, end.other_id)}"
        ctx.findings.note(
            ReportKind.EXCLUDED_LINK, element, "the target is in an excluded package, so no slot"
        )
        return None
    if why == LEFT_OUTSIDE:
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


def _is_owned(end: UmlLinkEnd, owned: set[tuple[int, int]]) -> bool:
    """Whether the slot an end gives is owned: a composite end, or a pair a boundary makes owned."""
    return bool(end.owned_by_composite) or (end.holder_id, end.other_id) in owned


def _end_usage(
    ctx: Context, link: UmlLink, end: UmlLinkEnd, owned: set[tuple[int, int]]
) -> Usage | None:
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
    target_range = _range_of(ctx, end, holder, slot)
    if bounds is None or target_range is None:
        return None
    described_as = (target_range, described(ctx, element, link.note))
    shape = shape_of(slot, described_as, bounds, owned=_is_owned(end, owned))
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


def _refused(ctx: Context, link: UmlLink) -> bool:
    """A connector no rule maps (see ``_refusal``), or one with no role at all."""
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
        owned_by_composite=link.source_aggregate == COMPOSITE,
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


def link_usages(ctx: Context, model: UmlModel, owned: set[tuple[int, int]]) -> list[Usage]:
    """The slots of every association and dependency, in connector order."""
    usages: list[Usage] = []
    for link in sorted(model.uml_links or [], key=lambda each: each.connector_id):
        if link.link_kind == UmlLinkKind.GENERALISATION or _refused(ctx, link):
            continue
        if link.link_kind == UmlLinkKind.DEPENDENCY and not _dependency_target_ok(ctx, link):
            continue
        made = (_end_usage(ctx, link, end, owned) for end in _ends(link))
        usages.extend(usage for usage in made if usage is not None)
    return usages
