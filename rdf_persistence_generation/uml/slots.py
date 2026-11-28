"""Slots (R-5, R-6, R-8, R-11, R-13, R-24; PD-7, PD-8, PD-13, PD-15, PD-16; D-10..D-12).

A *usage* is one slot on one class, with the shape it has there (``shape_of``, a slot). ``attribute_usages`` and
``link_usages`` read them from the model; ``share`` makes one slot of the usages of a name and a
``slot_usage`` wherever the shape differs.
"""

import re
from collections.abc import Mapping
from typing import Final

from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence_generation.generated.rp_generation import (
    ReportKind,
    UmlAttribute,
    UmlElement,
    UmlName,
    UmlRule,
)
from rdf_persistence_generation.uml.classes import annotation, description_of
from rdf_persistence_generation.uml.context import Context, literals_of, local_of, path_of
from rdf_persistence_generation.uml.modules import ModulePath
from rdf_persistence_generation.uml.naming import (
    check_local_name,
    check_slot_name,
    slot_name,
    title_for,
)

URI: Final = "uri"
OWNED: Final = RpAnnotation.OWNED.value
LOADED_GRAPH: Final = RpAnnotation.RP_LOADED_GRAPH.value  # an «own graph» slot (PD-9)
ANNOTATED: Final = (OWNED, LOADED_GRAPH)  # the shape fields a slot states as an annotation
HAS_PART: Final = "has_part"  # the toolkit slot of a collection's members (dcterms:hasPart)
MEMBER_CLASS: Final = "member_class"  # the toolkit slot a reference collection's member role fixes
MULTIPLICITY: Final = (
    "multiplicity"  # the name of the slot that carries a multiplicity's limits only
)
COMPOSITE: Final = 2
FROM_ATTRIBUTE: Final = 0  # the first of a usage's ``order`` for a slot an attribute gave
FROM_LINK: Final = 1  # ... for a slot an association or a dependency gave
UNSPECIFIED: Final = "0..*"
_RANGE_ONLY = re.compile(r"(\d+)\.\.(\d+|\*)")
_EXACT = re.compile(r"\d+")
_MANY = "*"
_MINIMUM: Final = "minimum_cardinality"
_MAXIMUM: Final = "maximum_cardinality"
LANG_STRINGS: Final = ("rdf:langString", "rdf:PlainLiteral")
XSD: Final[dict[str, tuple[str, int | None]]] = {
    "xsd:string": ("string", None),
    "xsd:normalizedString": ("string", None),
    "xsd:anyURI": (URI, None),
    "xsd:boolean": ("boolean", None),
    "xsd:date": ("date", None),
    "xsd:dateTime": ("datetime", None),
    "xsd:time": ("time", None),
    "xsd:integer": ("integer", None),
    "xsd:int": ("integer", None),
    "xsd:long": ("integer", None),
    "xsd:nonNegativeInteger": ("integer", 0),
    "xsd:positiveInteger": ("integer", 1),
    "xsd:decimal": ("decimal", None),
    "xsd:double": ("double", None),
    "xsd:float": ("float", None),
}


def _flag(value: bool) -> bool | None:
    """A LinkML flag: True when it holds, unset (not False) when it does not, as the output states it."""
    return True if value else None


def parse_bounds(text: str) -> SlotDefinition | None:
    """``l..u``, ``n`` or ``*`` as the slot flags a multiplicity gives (D-11); None for anything else.

    The slot carries the limits only, ``required``, ``multivalued`` and the two cardinalities, under the name
    ``MULTIPLICITY``; ``shape_of`` copies them. A ``u`` below ``l`` is not a multiplicity.
    """
    text = text.strip()
    if text == _MANY:
        return SlotDefinition(name=MULTIPLICITY, multivalued=True)
    if _EXACT.fullmatch(text):
        return _bounds(int(text), int(text))
    match = _RANGE_ONLY.fullmatch(text)
    if match is None:
        return None
    upper = None if match.group(2) == _MANY else int(match.group(2))
    lower = int(match.group(1))
    return None if upper is not None and upper < lower else _bounds(lower, upper)


def _bounds(lower: int, upper: int | None) -> SlotDefinition:
    many = upper is None or upper > 1
    return SlotDefinition(
        name=MULTIPLICITY,
        required=_flag(lower >= 1),
        multivalued=_flag(many),
        minimum_cardinality=lower if lower > 1 else None,
        maximum_cardinality=upper if upper is not None and upper > 1 else None,
    )


SHAPE_FIELDS: Final = (
    "range",
    "required",
    "multivalued",
    "description",
    "minimum_cardinality",
    "maximum_cardinality",
    "minimum_value",
    OWNED,
    LOADED_GRAPH,
)
# What the slot states only when every usage agrees; ``range`` and ``description`` always follow PD-16.
LIMIT_FIELDS: Final = tuple(each for each in SHAPE_FIELDS if each not in ("range", "description"))
# The boolean limits a usage writes as ``false`` when they differ, so it does not inherit a ``true``.
EXPLICIT_FLAGS: Final = frozenset({"required", "multivalued"})


def shape_of(
    name: str,
    range_and_description: tuple[str, str | None],
    bounds: SlotDefinition,
    minimum_value: int | None = None,
    marked: tuple[str, ...] = (),
) -> SlotDefinition:
    """What a slot looks like on one class, as a slot named ``name``: the fields that may differ from one class to the next.

    ``bounds`` gives the multiplicity's limits. A metaslot has no ``owned``, so an owned slot carries the
    ``owned`` annotation that the output states too (``is_owned`` reads it); a slot of an «own graph»
    composition carries ``rp_loaded_graph`` the same way (PD-9). ``marked`` names the annotations
    (``ANNOTATED``) the slot carries.
    """
    range_, description = range_and_description
    return SlotDefinition(
        name=name,
        range=range_,
        description=description,
        required=bounds.required,
        multivalued=bounds.multivalued,
        minimum_cardinality=bounds.minimum_cardinality,
        maximum_cardinality=bounds.maximum_cardinality,
        minimum_value=minimum_value,
        annotations={tag: annotation(tag, "true") for tag in marked},
    )


def is_owned(shape: SlotDefinition) -> bool:
    """Whether a shape is an owned slot: it carries the ``owned`` annotation."""
    return OWNED in shape.annotations


class Usage:
    """One slot on one class: its identity, where in the class it sits and its shape there.

    ``identity`` is the slot's name, explicit ``slot_uri`` and title; ``written`` is the UML name it was
    written as, with the IRI it expands to (the one a toolkit slot is found by).
    """

    __slots__ = ("holder", "identity", "order", "shape", "written")

    def __init__(
        self,
        holder: UmlElement,
        identities: tuple[SlotDefinition, UmlName],
        order: tuple[int, int, str],
        shape: SlotDefinition,
    ) -> None:
        self.holder = holder
        self.identity, self.written = identities
        self.order = order
        self.shape = shape

    @property
    def name(self) -> str:
        return str(self.identity.name)

    @property
    def iri(self) -> str:
        return str(self.written.iri)


def _value(shape: SlotDefinition, field_name: str) -> object:
    return (
        field_name in shape.annotations if field_name in ANNOTATED else getattr(shape, field_name)
    )


def _shape_kwargs(shape: SlotDefinition, only: set[str] | frozenset[str]) -> dict[str, object]:
    """The LinkML keywords of the ``only`` fields of a shape; an unset or false field writes nothing."""
    kwargs: dict[str, object] = {}
    notes = {}
    for field_name in SHAPE_FIELDS:
        value = _value(shape, field_name)
        if field_name in only and value is not None and value is not False:
            if field_name in ANNOTATED:
                notes[field_name] = annotation(field_name, str(value).lower())
            kwargs.update(_keyword(field_name, value, shape))
    return {**kwargs, "annotations": notes} if notes else kwargs


def _keyword(name: str, value: object, shape: SlotDefinition) -> dict[str, object]:
    if name == LOADED_GRAPH:
        return {}
    if name == OWNED:
        return {("inlined_as_list" if shape.multivalued else "inlined"): bool(value) or None}
    return {name: value}


def _comparable(shape: SlotDefinition, field_name: str) -> tuple[object, object]:
    """A field's value; an owned one also counts its multiplicity, which picks ``inlined`` or ``inlined_as_list``."""
    value = _value(shape, field_name)
    return (value, bool(shape.multivalued) if field_name == OWNED and value else None)


def differing_fields(shapes: list[SlotDefinition]) -> frozenset[str]:
    """The limits on which the usages of one slot do not all agree."""
    return frozenset(
        field_name
        for field_name in LIMIT_FIELDS
        if len({_comparable(shape, field_name) for shape in shapes}) > 1
    )


def slot_of(
    identity: SlotDefinition, shapes: list[SlotDefinition], differing: frozenset[str]
) -> SlotDefinition:
    """The slot of a name (R-13, PD-16).

    It states the limits every usage agrees on, the first usage's range and the first non-empty
    description, the usages being in PD-16 order.
    """
    description = next((shape.description for shape in shapes if shape.description), None)
    return SlotDefinition(
        name=identity.name,
        slot_uri=identity.slot_uri,
        title=identity.title,
        **_shape_kwargs(shapes[0], frozenset(LIMIT_FIELDS) - differing),
        range=shapes[0].range,
        description=description,
    )


def own_minimum(shape: SlotDefinition) -> int:
    """The lower bound a shape's multiplicity gives: the stored minimum, else 1 when required, else 0 (D-7)."""
    if shape.minimum_cardinality is not None:
        return int(shape.minimum_cardinality)
    return 1 if shape.required else 0


def own_maximum(shape: SlotDefinition) -> int | None:
    """The upper bound a shape's multiplicity gives: the stored maximum, else 1 when single-valued, else None (D-7).

    ``None`` is unbounded. A single-valued ``0..1`` stores no maximum, so this is not ``maximum_cardinality``.
    """
    if shape.maximum_cardinality is not None:
        return int(shape.maximum_cardinality)
    return None if shape.multivalued else 1


def usage_of(
    name: str, shape: SlotDefinition, differing: frozenset[str], slot: SlotDefinition
) -> SlotDefinition | None:
    """The ``slot_usage`` of a class: what it has of its own, or None.

    That is its value of each differing limit, its range when it is not the slot's and its description
    when it is non-empty and not the slot's; an empty description inherits the slot's. A differing
    ``required`` or ``multivalued`` is written ``false`` too, because an omitted flag inherits the
    parent's ``true`` (D-5). A differing cardinality is the usage's own bound (D-7): an unset one would
    inherit the ancestor's, and an unbounded maximum is not written.
    """
    kwargs = _shape_kwargs(shape, differing)
    for flag in EXPLICIT_FLAGS & differing:
        kwargs[flag] = bool(getattr(shape, flag))
    if _MINIMUM in differing:
        kwargs[_MINIMUM] = own_minimum(shape)
    if _MAXIMUM in differing:
        maximum = own_maximum(shape)
        if maximum is None:
            kwargs.pop(_MAXIMUM, None)
        else:
            kwargs[_MAXIMUM] = maximum
    if shape.range != slot.range:
        kwargs["range"] = shape.range
    if shape.description and shape.description != slot.description:
        kwargs["description"] = shape.description
    return SlotDefinition(name=name, **kwargs) if kwargs else None


def slot_identity(
    ctx: Context, name: UmlName, element: str
) -> tuple[SlotDefinition, UmlName] | None:
    """The identity of the slot a written name gives (PD-6, D-14); a name that breaks the lint is a problem.

    It is the slot's ``name``, explicit ``slot_uri`` and ``title`` as a slot, and the UML name it was
    written as with the IRI it expands to: LinkML has no metaslot for either, so ``UmlName`` holds them.
    """
    snake = slot_name(name.name)
    problem = check_local_name(name.name, element, UmlRule.ATTRIBUTE_SLOT) or check_slot_name(
        snake, element
    )
    if problem is not None:
        ctx.findings.add(problem)
        return None
    iri = name.iri or ctx.default_namespace() + name.name
    differs = snake != name.name
    explicit = name.curie or (f"{ctx.settings.default_prefix}:{name.name}" if differs else None)
    identity = SlotDefinition(name=snake, slot_uri=explicit, title=title_for(name.name))
    return identity, UmlName(name=name.name, iri=iri)


def _typed_by_not_generated(
    ctx: Context, element: str, attribute: UmlAttribute, declared: str
) -> bool:
    """Whether the type is an enumeration the run does not generate: no slot, one report line (R-30)."""
    if not ctx.not_generated_enum(attribute.classifier_id):
        return False
    ctx.findings.note(
        ReportKind.NOT_GENERATED,
        element,
        f"typed by {declared}, which is not generated, so no slot (R-30)",
    )
    return True


def _typed(
    ctx: Context, holder: UmlElement, attribute: UmlAttribute
) -> tuple[str, int | None] | None:
    """The range and ``minimum_value`` an attribute's type gives (PD-7, D-10, D-12), or None with a problem."""
    element = f"{holder.label}.{local_of(attribute.name)}"
    declared = (attribute.declared_type or "").strip()
    if _typed_by_not_generated(ctx, element, attribute, declared):
        return None
    target = ctx.elements.get(attribute.classifier_id or -1) or _enum_named(ctx, declared)
    if target is not None and target.is_enum:
        return (target.label if literals_of(target) else URI), None
    return _plain_type(ctx, element, declared)


def _plain_type(ctx: Context, element: str, declared: str) -> tuple[str, int | None] | None:
    if declared in LANG_STRINGS:
        ctx.findings.no_rule(element, f"{declared} has no toolkit range yet (#209)")
    elif declared in XSD:
        return XSD[declared]
    else:
        ctx.findings.no_rule(element, f"type {declared or 'none'}")
    return None


def _enum_named(ctx: Context, declared: str) -> UmlElement | None:
    return next((e for e in ctx.elements.values() if e.is_enum and e.label == declared), None)


def attribute_bounds(ctx: Context, element: str, attribute: UmlAttribute) -> SlotDefinition | None:
    """The bounds of an attribute as stored; both missing is the unspecified multiplicity (D-11)."""
    if attribute.lower_bound is None and attribute.upper_bound is None:
        ctx.findings.note(ReportKind.UNSPECIFIED_MULTIPLICITY, element, f"read as {UNSPECIFIED}")
        return parse_bounds(UNSPECIFIED)
    text = f"{attribute.lower_bound or 0}..{attribute.upper_bound or _MANY}"
    return check_bounds(ctx, element, text)


def check_bounds(ctx: Context, element: str, text: str) -> SlotDefinition | None:
    bounds = parse_bounds(text)
    if bounds is None:
        ctx.findings.no_rule(element, f"multiplicity {text}")
    return bounds


def _attribute_usage(ctx: Context, holder: UmlElement, attribute: UmlAttribute) -> Usage | None:
    element = f"{holder.label}.{local_of(attribute.name)}"
    name = ctx.resolve(attribute.name, element)
    identities = slot_identity(ctx, name, element) if name is not None else None
    typed = _typed(ctx, holder, attribute)
    bounds = attribute_bounds(ctx, element, attribute)
    if attribute.uml_stereotype:
        ctx.findings.note(
            ReportKind.IGNORED_STEREOTYPE,
            element,
            f"stereotype {attribute.uml_stereotype} is not used",
        )
    if identities is None or typed is None or bounds is None:
        return None
    description = description_of(attribute.note)
    name_of_slot = str(identities[0].name)
    shape = shape_of(name_of_slot, (typed[0], description), bounds, typed[1])
    return Usage(holder, identities, (FROM_ATTRIBUTE, attribute.position or 0, name_of_slot), shape)


class SharedSlots:
    """The slots of a run: each defined once, in a home module, with the ``slot_usage`` of each class."""

    def __init__(self) -> None:
        self.definitions: dict[str, SlotDefinition] = {}
        self.home: dict[str, str] = {}
        self.class_usage: dict[str, dict[str, SlotDefinition]] = {}
        self.toolkit_imports: dict[
            str, set[str]
        ] = {}  # class label -> toolkit modules its slots need


def _check_one_iri(ctx: Context, name: str, usages: list[Usage]) -> None:
    iris = sorted({usage.iri for usage in usages})
    if len(iris) > 1:
        ctx.findings.problem(UmlRule.CLASS_IRI, name, f"{iris[0]} and {iris[1]} both map to {name}")


def _used_in(usages: list[Usage]) -> dict[str, set[ModulePath]]:
    """The modules each slot name is used in: a package is its own module."""
    found: dict[str, set[ModulePath]] = {}
    for usage in usages:
        found.setdefault(usage.name, set()).add(path_of(usage.holder))
    return found


def choose_homes(
    usages: list[Usage], reach: Mapping[ModulePath, set[ModulePath]]
) -> dict[str, ModulePath | None]:
    """The home module of each slot used in several modules (R-24, PD-16).

    It is the one every other using module reaches by imports; when several qualify, the first in path
    order; None when none does.
    """
    homes: dict[str, ModulePath | None] = {}
    for name, modules in _used_in(usages).items():
        if len(modules) > 1:
            fits = sorted(m for m in modules if all(m in reach[other] for other in modules - {m}))
            homes[name] = fits[0] if fits else None
    return homes


def shared_edges(
    usages: list[Usage],
    homes: Mapping[str, ModulePath | None],
    by_label: Mapping[str, UmlElement],
) -> dict[ModulePath, set[ModulePath]]:
    """The imports a shared slot adds: each using module imports the home, which imports its range's module."""
    added: dict[ModulePath, set[ModulePath]] = {}
    for name, modules in _used_in(usages).items():
        home = homes.get(name)
        if home is None:
            continue
        for other in modules - {home}:
            added.setdefault(other, set()).add(home)
        first = min(
            (each for each in usages if each.name == name),
            key=lambda each: (path_of(each.holder), each.holder.label, each.order),
        )
        target = by_label.get(first.shape.range)
        if target is not None:
            added.setdefault(home, set()).add(path_of(target))
    return added


def _no_home(ctx: Context, name: str, modules: list[str]) -> None:
    ctx.findings.problem(
        UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
        name,
        f"used in {', '.join(modules)} and no one of them is imported by the others",
    )


def _place_key(module_of: Mapping[int, str], usage: Usage) -> tuple[str, str, tuple[int, int, str]]:
    """Where a usage sits in PD-16 order: its module, its class, its place in the class."""
    return (module_of[usage.holder.uml_class.object_id], usage.holder.label, usage.order)


def _ancestor_bound(
    usage: Usage, held: Mapping[str, Usage], lineage: tuple[Mapping[int, str], Mapping[str, int]]
) -> tuple[str, int] | None:
    """The nearest ``is_a`` ancestor that draws the same slot with a finite maximum, and that maximum (D-8).

    The walk goes by label through every class, those with no attributes included, and stops on a cycle.
    """
    parent_of, ids_by_label = lineage
    label, seen = usage.holder.label, {usage.holder.label}
    while (label := parent_of.get(ids_by_label.get(label, -1), "")) and label not in seen:
        seen.add(label)
        ancestor = held.get(label)
        bound = own_maximum(ancestor.shape) if ancestor is not None else None
        if bound is not None:
            return label, bound
    return None


def _check_unbounded(
    ctx: Context,
    name: str,
    ordered: list[Usage],
    lineage: tuple[Mapping[int, str], Mapping[str, int]],
    differing: frozenset[str],
) -> None:
    """An unbounded role cannot redraw a bounded ``is_a`` ancestor's (D-8, DEC-5); only a differing maximum can."""
    if _MAXIMUM not in differing:
        return
    held = {each.holder.label: each for each in ordered}
    for each in ordered:
        found = _ancestor_bound(each, held, lineage) if own_maximum(each.shape) is None else None
        if found is not None:
            ancestor, bound = found
            ctx.findings.problem(
                UmlRule.CARDINALITY_UNBOUNDED,
                f"{each.holder.label}.{name}",
                f"{ancestor}.{name} is bounded at {bound}, and an unbounded role cannot redraw a bounded one: "
                "bound the role or unbind the ancestor's",
            )


def share(
    ctx: Context,
    usages: list[Usage],
    module_of: dict[int, str],
    homes: Mapping[str, str | None],
    lineage: tuple[Mapping[int, str], Mapping[str, int]],
) -> SharedSlots:
    """One slot for each name (R-13): the slot states what every usage agrees on, each class its own rest.

    ``homes`` names the module that defines each slot used in several modules (``choose_homes``);
    ``lineage`` is ``parent_of`` (object id to parent label) and the object id of each class label.
    """
    shared = SharedSlots()
    by_name: dict[str, list[Usage]] = {}
    for usage in usages:
        by_name.setdefault(usage.name, []).append(usage)
    for name in sorted(by_name):
        ordered = sorted(by_name[name], key=lambda each: _place_key(module_of, each))
        _check_one_iri(ctx, name, ordered)
        modules = sorted({module_of[u.holder.uml_class.object_id] for u in ordered})
        if len(modules) > 1 and homes.get(name) is None:
            _no_home(ctx, name, modules)
        first = ordered[0]
        shapes = [each.shape for each in ordered]
        differing = differing_fields(shapes)
        slot = slot_of(first.identity, shapes, differing)
        _check_unbounded(ctx, name, ordered, lineage, differing)
        shared.definitions[name] = slot
        shared.home[name] = homes.get(name) or module_of[first.holder.uml_class.object_id]
        for each in ordered:
            narrowed = usage_of(name, each.shape, differing, slot)
            if narrowed is not None:
                shared.class_usage.setdefault(each.holder.label, {})[name] = narrowed
    return shared


def split_toolkit(ctx: Context, usages: list[Usage]) -> tuple[list[Usage], list[Usage]]:
    """The usages whose IRI is a toolkit slot's ``slot_uri`` (R-15), and the others (PD-18).

    ``id`` is not found by IRI (it is the identifier), so ``dct:identifier`` stays a new slot (R-22).
    """
    known = [each for each in usages if ctx.toolkit.slot_by_uri(each.iri) is not None]
    return known, [each for each in usages if each not in known]


def name_slots(ctx: Context, generated: list[Usage], toolkit: list[Usage]) -> None:
    """Record, for each class, the slot each name a modeller wrote stands for (PD-21).

    A slot is known by its slot name and by its UML name; a usage that reuses a toolkit slot stands for
    the toolkit's slot.
    """
    for usage in generated:
        _alias(ctx, usage, usage.name)
    for usage in toolkit:
        found = ctx.toolkit.slot_by_uri(usage.iri)
        if found is not None:
            _alias(ctx, usage, str(found.name))


def _alias(ctx: Context, usage: Usage, slot: str) -> None:
    held = ctx.slot_aliases.setdefault(usage.holder.uml_class.object_id, {})
    held[slot] = held[usage.name] = slot
    if usage.written.name:
        held[usage.written.name] = slot


def _cardinality_text(shape: SlotDefinition) -> str:
    lower = shape.minimum_cardinality or int(bool(shape.required))
    upper = shape.maximum_cardinality or (_MANY if shape.multivalued else 1)
    return f"{lower}..{upper}"


def _kept(
    ctx: Context, element: str, slot: SlotDefinition, shape: SlotDefinition, member: bool
) -> None:
    """Report each way the UML shape differs from the toolkit slot, which is kept (PD-18).

    A ``member`` role's range is carried, as the member class, so it is not reported (#241).
    """
    name = str(slot.name)
    differences = {"multivalued": (bool(shape.multivalued), bool(slot.multivalued))}
    if not member:
        differences["range"] = (shape.range, slot.range)
    for what, (uml, toolkit) in differences.items():
        if toolkit is not None and uml != toolkit:
            ctx.findings.note(
                ReportKind.TOOLKIT_SLOT_KEPT,
                element,
                f"the toolkit's {name} is kept; {what} {str(uml).lower()} is not carried",
            )


def _toolkit_names(ctx: Context, definition: ClassDefinition) -> list[str]:
    """The toolkit classes a class is built on: its ``is_a`` and mixins that the toolkit defines."""
    named = [definition.is_a, *definition.mixins]
    return [name for name in named if name and ctx.toolkit.class_by_name(name)]


def _use_toolkit_slot(
    ctx: Context,
    usage: Usage,
    definition: ClassDefinition,
    shared: SharedSlots,
    slot_names: dict[int, list[str]],
) -> bool:
    """Use the toolkit slot for the usage; False when the toolkit fills it, so nothing is carried."""
    slot = ctx.toolkit.toolkit_slot(usage.iri)
    name, label, shape = str(slot.name), usage.holder.label, usage.shape
    if ctx.toolkit.is_filled(name):
        text = f"the toolkit fills {name}; [{_cardinality_text(shape)}] is not carried"
        ctx.findings.note(ReportKind.TOOLKIT_FILLED, f"{label}.{name}", text)
        return False
    sources = _toolkit_names(ctx, definition)
    held = slot_names.setdefault(usage.holder.uml_class.object_id, [])
    if not ctx.toolkit.inherits(sources, name) and name not in held:
        held.append(name)
        shared.toolkit_imports.setdefault(label, set()).add(ctx.toolkit.module_of_slot(name))
    if shape.required and not ctx.toolkit.required_on(sources, name):
        shared.class_usage.setdefault(label, {})[name] = SlotDefinition(name=name, required=True)
    return True


def use_toolkit_slots(
    ctx: Context,
    usages: list[Usage],
    classes: dict[int, ClassDefinition],
    shared: SharedSlots,
    slot_names: dict[int, list[str]],
) -> None:
    """Give each class the toolkit slots its usages stand for (R-15, PD-18, PD-26).

    The toolkit slot is not defined again: the class lists it unless a toolkit class it is built on brings it,
    its module is imported, and a ``slot_usage`` states ``required`` only where the toolkit's is not. A
    toolkit-filled slot is dropped and reported. A reference collection's member role fixes its
    ``member_class`` (``_member_roles``).
    """
    members = _member_roles(ctx, usages, classes)
    for usage in sorted(usages, key=lambda each: (each.holder.label, each.order)):
        definition = classes[usage.holder.uml_class.object_id]
        if _use_toolkit_slot(ctx, usage, definition, shared, slot_names):
            slot = ctx.toolkit.toolkit_slot(usage.iri)
            _kept(ctx, f"{usage.holder.label}.{slot.name}", slot, usage.shape, id(usage) in members)
    _fix_member_classes(ctx, [each for each in usages if id(each) in members], shared)


def _is_collection(
    ctx: Context, definition: ClassDefinition, by_name: Mapping[str, ClassDefinition]
) -> bool:
    """Whether a toolkit class the class is built on, itself or through a domain ``is_a``, has ``member_class``.

    The toolkit's metamodel says which classes are reference collections, never a name here.
    """
    seen: set[str] = set()
    current: ClassDefinition | None = definition
    while current is not None and current.name not in seen:
        if ctx.toolkit.inherits(_toolkit_names(ctx, current), MEMBER_CLASS):
            return True
        seen.add(str(current.name))
        current = by_name.get(current.is_a) if current.is_a else None
    return False


def _member_roles(
    ctx: Context, usages: list[Usage], classes: Mapping[int, ClassDefinition]
) -> set[int]:
    """The ids of the ``dct:hasPart`` usages that name a collection's member class (#241, #260).

    The holder is a reference collection and the range a converted class. The roles to a class other
    than the holder are the member candidates. A lone role to the holder's own class is the member
    role too (DEC-2), unless another collection in the holder's ``is_a`` lineage has a member role
    (OPEN-6): then it is nesting and stays the toolkit's ``has_part``. A self-role beside a role to
    another class is nesting.
    """
    by_name = {str(each.name): each for each in classes.values()}
    members: list[Usage] = []
    selves: list[Usage] = []
    for usage in usages:
        slot = ctx.toolkit.slot_by_uri(usage.iri)
        target = usage.shape.range
        if (
            slot is not None
            and slot.name == HAS_PART
            and target in by_name
            and _is_collection(ctx, classes[usage.holder.uml_class.object_id], by_name)
        ):
            (selves if target == usage.holder.label else members).append(usage)
    members += _lone_self_roles(selves, {each.holder.label for each in members}, by_name)
    return {id(each) for each in _without_narrowed_parents(ctx, members, by_name)}


def _lone_self_roles(
    selves: list[Usage], holders: set[str], by_name: Mapping[str, ClassDefinition]
) -> list[Usage]:
    """The self-roles whose holder shares no ``is_a`` lineage with a holder of a member role (OPEN-6)."""
    return [
        usage
        for usage in selves
        if not any(
            other in _lineage(usage.holder.label, by_name)
            or usage.holder.label in _lineage(other, by_name)
            for other in holders
        )
    ]


def _lineage(name: str, by_name: Mapping[str, ClassDefinition]) -> list[str]:
    """The class and its domain ``is_a`` ancestors, nearest first."""
    found: list[str] = []
    current: str | None = name
    while current is not None and current in by_name and current not in found:
        found.append(current)
        current = by_name[current].is_a
    return found


def _without_narrowed_parents(
    ctx: Context, members: list[Usage], by_name: Mapping[str, ClassDefinition]
) -> list[Usage]:
    """Drop the member role of an abstract collection whose subclass draws its own (#274).

    Both fixing ``member_class`` contradict each other, so the parent's role stays the toolkit's
    ``has_part`` and each subclass fixes its own. A subclass's member class that does not descend
    from its parent's is a problem naming both.
    """
    targets = {each.holder.label: str(each.shape.range) for each in members}
    narrowed: set[str] = set()
    for label in sorted(targets):
        parent = next((each for each in _lineage(label, by_name)[1:] if each in targets), None)
        if parent is None:
            continue
        if targets[parent] not in _lineage(targets[label], by_name):
            ctx.findings.problem(
                UmlRule.TOOLKIT_SLOT,
                label,
                f"dct:hasPart role to {targets[label]} does not narrow {parent}'s member class "
                f"{targets[parent]}: a subclass's member class descends from its parent's",
            )
        if by_name[parent].abstract:
            narrowed.add(parent)
    return [each for each in members if each.holder.label not in narrowed]


def _fix_member_classes(ctx: Context, members: list[Usage], shared: SharedSlots) -> None:
    """Fix each collection's ``member_class`` to its member role's class; two classes are a problem."""
    by_holder: dict[str, set[str]] = {}
    for usage in members:
        by_holder.setdefault(usage.holder.label, set()).add(str(usage.shape.range))
    for label, targets in sorted(by_holder.items()):
        if len(targets) > 1:
            ctx.findings.problem(
                UmlRule.TOOLKIT_SLOT,
                label,
                f"dct:hasPart roles to {' and '.join(sorted(targets))}: "
                "a reference collection has one member class",
            )
            continue
        shared.class_usage.setdefault(label, {})[MEMBER_CLASS] = SlotDefinition(
            name=MEMBER_CLASS, equals_string=targets.pop()
        )


def attribute_usages(ctx: Context, holder: UmlElement) -> list[Usage]:
    """The slots of a class's attributes, in position order."""
    ordered = sorted(
        holder.uml_class.uml_attributes or [],
        key=lambda each: (each.position or 0, each.attribute_id),
    )
    usages = (_attribute_usage(ctx, holder, attribute) for attribute in ordered)
    return [usage for usage in usages if usage is not None]
