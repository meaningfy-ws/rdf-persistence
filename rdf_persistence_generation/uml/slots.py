"""Slots (R-5, R-6, R-8, R-11, R-13; PD-7, PD-8, PD-13, PD-15, PD-16 single-module part; D-10..D-12).

A *usage* is one slot on one class, with the shape it has there (``Shape``). ``attribute_usages`` and
``link_usages`` read them from the model; ``share`` makes one slot of the usages of a name and a
``slot_usage`` wherever the shape differs.
"""

import re
from typing import Final

from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition

from rdf_persistence_generation.generated.rp_generation import (
    ReportKind,
    UmlAttribute,
    UmlName,
    UmlRule,
)
from rdf_persistence_generation.uml.classes import annotation, description_of
from rdf_persistence_generation.uml.context import Context, Element, local_of
from rdf_persistence_generation.uml.naming import check_slot_name, slot_name, title_for

URI: Final = "uri"
OWNED: Final = "owned"
COMPOSITE: Final = 2
UNSPECIFIED: Final = "0..*"
_RANGE_ONLY = re.compile(r"(\d+)\.\.(\d+|\*)")
_EXACT = re.compile(r"\d+")
_MANY = "*"
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


class Bounds:
    """A multiplicity as the slot flags: ``required``, ``multivalued`` and the two cardinalities (D-11)."""

    __slots__ = ("maximum", "minimum", "multivalued", "required")

    def __init__(
        self, required: bool, multivalued: bool, minimum: int | None, maximum: int | None
    ) -> None:
        self.required = required
        self.multivalued = multivalued
        self.minimum = minimum
        self.maximum = maximum


def parse_bounds(text: str) -> Bounds | None:
    """``l..u``, ``n`` or ``*`` as ``Bounds``; None for anything else, or ``u`` below ``l``."""
    text = text.strip()
    if text == _MANY:
        return Bounds(False, True, None, None)
    if _EXACT.fullmatch(text):
        return _bounds(int(text), int(text))
    match = _RANGE_ONLY.fullmatch(text)
    if match is None:
        return None
    upper = None if match.group(2) == _MANY else int(match.group(2))
    lower = int(match.group(1))
    return None if upper is not None and upper < lower else _bounds(lower, upper)


def _bounds(lower: int, upper: int | None) -> Bounds:
    many = upper is None or upper > 1
    return Bounds(
        required=lower >= 1,
        multivalued=many,
        minimum=lower if lower > 1 else None,
        maximum=upper if upper is not None and upper > 1 else None,
    )


SHAPE_FIELDS: Final = (
    "range",
    "required",
    "multivalued",
    "description",
    "minimum_cardinality",
    "maximum_cardinality",
    "minimum_value",
    "owned",
)
# What the slot states only when every usage agrees; ``range`` and ``description`` always follow PD-16.
LIMIT_FIELDS: Final = tuple(each for each in SHAPE_FIELDS if each not in ("range", "description"))


class Shape:
    """What a slot looks like on one class; the fields that may differ from one class to the next."""

    __slots__ = SHAPE_FIELDS

    def __init__(
        self,
        range_and_description: tuple[str, str | None],
        bounds: Bounds,
        minimum_value: int | None = None,
        owned: bool = False,
    ) -> None:
        self.range, self.description = range_and_description
        self.required = bounds.required
        self.multivalued = bounds.multivalued
        self.minimum_cardinality = bounds.minimum
        self.maximum_cardinality = bounds.maximum
        self.minimum_value = minimum_value
        self.owned = owned


class Usage:
    """One slot on one class: its identity, where in the class it sits and its shape there."""

    __slots__ = ("holder", "identity", "order", "shape")

    def __init__(
        self, holder: Element, identity: "Identity", order: tuple[int, int, str], shape: Shape
    ) -> None:
        self.holder = holder
        self.identity = identity
        self.order = order
        self.shape = shape

    @property
    def name(self) -> str:
        return self.identity.name


def _shape_kwargs(shape: Shape, only: set[str] | frozenset[str]) -> dict[str, object]:
    """The LinkML keywords of the ``only`` fields of a shape; an unset or false field writes nothing."""
    kwargs: dict[str, object] = {}
    for field_name in SHAPE_FIELDS:
        value = getattr(shape, field_name)
        if field_name in only and value is not None and value is not False:
            kwargs.update(_keyword(field_name, value, shape))
    return kwargs


def _keyword(name: str, value: object, shape: Shape) -> dict[str, object]:
    if name == OWNED:
        inline = "inlined_as_list" if shape.multivalued else "inlined"
        return {
            "annotations": {OWNED: annotation(OWNED, str(value).lower())},
            inline: bool(value) or None,
        }
    return {name: value}


def _comparable(shape: Shape, field_name: str) -> tuple[object, object]:
    """A field's value; an owned one also counts its multiplicity, which picks ``inlined`` or ``inlined_as_list``."""
    value = getattr(shape, field_name)
    return (value, shape.multivalued if field_name == OWNED and value else None)


def differing_fields(shapes: list[Shape]) -> frozenset[str]:
    """The limits on which the usages of one slot do not all agree."""
    return frozenset(
        field_name
        for field_name in LIMIT_FIELDS
        if len({_comparable(shape, field_name) for shape in shapes}) > 1
    )


def slot_of(identity: "Identity", shapes: list[Shape], differing: frozenset[str]) -> SlotDefinition:
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


def usage_of(
    name: str, shape: Shape, differing: frozenset[str], slot: SlotDefinition
) -> SlotDefinition | None:
    """The ``slot_usage`` of a class: what it has of its own, or None.

    That is its value of each differing limit, its range when it is not the slot's and its description
    when it is non-empty and not the slot's; an empty description inherits the slot's.
    """
    kwargs = _shape_kwargs(shape, differing)
    if shape.range != slot.range:
        kwargs["range"] = shape.range
    if shape.description and shape.description != slot.description:
        kwargs["description"] = shape.description
    return SlotDefinition(name=name, **kwargs) if kwargs else None


class Identity:
    """A slot's name, the IRI it expands to, its explicit ``slot_uri`` and its title."""

    __slots__ = ("iri", "name", "slot_uri", "title")

    def __init__(self, name: str, iri: str, slot_uri: str | None, title: str) -> None:
        self.name = name
        self.iri = iri
        self.slot_uri = slot_uri
        self.title = title


def slot_identity(ctx: Context, name: UmlName, element: str) -> Identity | None:
    """The identity of the slot a written name gives (PD-6, D-14); a name that breaks the lint is a problem."""
    snake = slot_name(name.name)
    problem = check_slot_name(snake, element)
    if problem is not None:
        ctx.findings.add(problem)
        return None
    iri = name.iri or ctx.default_namespace() + name.name
    differs = snake != name.name
    explicit = name.curie or (f"{ctx.settings.default_prefix}:{name.name}" if differs else None)
    return Identity(snake, iri, explicit, title_for(name.name))


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


def _typed(ctx: Context, holder: Element, attribute: UmlAttribute) -> tuple[str, int | None] | None:
    """The range and ``minimum_value`` an attribute's type gives (PD-7, D-10, D-12), or None with a problem."""
    element = f"{holder.label}.{local_of(attribute.name)}"
    declared = (attribute.declared_type or "").strip()
    if _typed_by_not_generated(ctx, element, attribute, declared):
        return None
    target = ctx.elements.get(attribute.classifier_id or -1) or _enum_named(ctx, declared)
    if target is not None and target.is_enum:
        return (target.label if target.literals else URI), None
    return _plain_type(ctx, element, declared)


def _plain_type(ctx: Context, element: str, declared: str) -> tuple[str, int | None] | None:
    if declared in LANG_STRINGS:
        ctx.findings.no_rule(element, f"{declared} has no toolkit range yet (#209)")
    elif declared in XSD:
        return XSD[declared]
    else:
        ctx.findings.no_rule(element, f"type {declared or 'none'}")
    return None


def _enum_named(ctx: Context, declared: str) -> Element | None:
    return next((e for e in ctx.elements.values() if e.is_enum and e.label == declared), None)


def attribute_bounds(ctx: Context, element: str, attribute: UmlAttribute) -> Bounds | None:
    """The bounds of an attribute as stored; both missing is the unspecified multiplicity (D-11)."""
    if attribute.lower_bound is None and attribute.upper_bound is None:
        ctx.findings.note(ReportKind.UNSPECIFIED_MULTIPLICITY, element, f"read as {UNSPECIFIED}")
        return parse_bounds(UNSPECIFIED)
    text = f"{attribute.lower_bound or 0}..{attribute.upper_bound or _MANY}"
    return check_bounds(ctx, element, text)


def check_bounds(ctx: Context, element: str, text: str) -> Bounds | None:
    bounds = parse_bounds(text)
    if bounds is None:
        ctx.findings.no_rule(element, f"multiplicity {text}")
    return bounds


def described(ctx: Context, element: str, note: str | None) -> str | None:
    """A note as a description; an empty one is a report line (PD-11)."""
    description = description_of(note)
    if description is None:
        ctx.findings.note(ReportKind.NO_NOTE, element, "no note, so no description")
    return description


def _attribute_usage(ctx: Context, holder: Element, attribute: UmlAttribute) -> Usage | None:
    element = f"{holder.label}.{local_of(attribute.name)}"
    name = ctx.resolve(attribute.name, element)
    identity = slot_identity(ctx, name, element) if name is not None else None
    typed = _typed(ctx, holder, attribute)
    bounds = attribute_bounds(ctx, element, attribute)
    if attribute.uml_stereotype:
        ctx.findings.note(
            ReportKind.IGNORED_STEREOTYPE,
            element,
            f"stereotype {attribute.uml_stereotype} is not used",
        )
    if identity is None or typed is None or bounds is None:
        return None
    description = described(ctx, element, attribute.note)
    shape = Shape((typed[0], description), bounds, typed[1])
    return Usage(holder, identity, (0, attribute.position or 0, identity.name), shape)


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
    iris = sorted({usage.identity.iri for usage in usages})
    if len(iris) > 1:
        ctx.findings.problem(UmlRule.CLASS_IRI, name, f"{iris[0]} and {iris[1]} both map to {name}")


def _check_one_module(ctx: Context, name: str, modules: list[str]) -> None:
    if len(modules) > 1:
        ctx.findings.problem(
            UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
            name,
            f"used in {', '.join(modules)}; slots shared across packages arrive in stage 2 (task 2.6)",
        )


def share(ctx: Context, usages: list[Usage], module_of: dict[int, str]) -> SharedSlots:
    """One slot for each name (R-13): the slot states what every usage agrees on, each class its own rest."""
    shared = SharedSlots()
    by_name: dict[str, list[Usage]] = {}
    for usage in usages:
        by_name.setdefault(usage.name, []).append(usage)
    for name in sorted(by_name):
        key = lambda each: (module_of[each.holder.uml.object_id], each.holder.label, each.order)  # noqa: E731
        ordered = sorted(by_name[name], key=key)
        _check_one_iri(ctx, name, ordered)
        _check_one_module(ctx, name, sorted({module_of[u.holder.uml.object_id] for u in ordered}))
        first = ordered[0]
        shapes = [each.shape for each in ordered]
        differing = differing_fields(shapes)
        slot = slot_of(first.identity, shapes, differing)
        shared.definitions[name] = slot
        shared.home[name] = module_of[first.holder.uml.object_id]
        for each in ordered:
            narrowed = usage_of(name, each.shape, differing, slot)
            if narrowed is not None:
                shared.class_usage.setdefault(each.holder.label, {})[name] = narrowed
    return shared


def split_toolkit(ctx: Context, usages: list[Usage]) -> tuple[list[Usage], list[Usage]]:
    """The usages whose IRI is a toolkit slot's ``slot_uri`` (R-15), and the others (PD-18).

    ``id`` is not found by IRI (it is the identifier), so ``dct:identifier`` stays a new slot (R-22).
    """
    known = [each for each in usages if ctx.toolkit.slot_by_uri(each.identity.iri) is not None]
    return known, [each for each in usages if each not in known]


def _cardinality_text(shape: Shape) -> str:
    lower = shape.minimum_cardinality or int(bool(shape.required))
    upper = shape.maximum_cardinality or (_MANY if shape.multivalued else 1)
    return f"{lower}..{upper}"


def _kept(ctx: Context, element: str, slot: SlotDefinition, shape: Shape) -> None:
    """Report each way the UML shape differs from the toolkit slot, which is kept (PD-18)."""
    name = str(slot.name)
    differences = {
        "multivalued": (shape.multivalued, bool(slot.multivalued)),
        "range": (shape.range, slot.range),
    }
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
) -> None:
    slot = ctx.toolkit.slot_by_uri(usage.identity.iri)
    assert slot is not None  # split_toolkit kept only usages that have one
    name, label, shape = str(slot.name), usage.holder.label, usage.shape
    element = f"{label}.{name}"
    if ctx.toolkit.is_filled(name):
        text = f"the toolkit fills {name}; [{_cardinality_text(shape)}] is not carried"
        ctx.findings.note(ReportKind.TOOLKIT_FILLED, element, text)
        return
    sources = _toolkit_names(ctx, definition)
    held = slot_names.setdefault(usage.holder.uml.object_id, [])
    if not ctx.toolkit.inherits(sources, name) and name not in held:
        held.append(name)
        shared.toolkit_imports.setdefault(label, set()).add(ctx.toolkit.module_of_slot(name))
    _kept(ctx, element, slot, shape)
    if shape.required and not ctx.toolkit.required_on(sources, name):
        shared.class_usage.setdefault(label, {})[name] = SlotDefinition(name=name, required=True)


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
    toolkit-filled slot is dropped and reported.
    """
    for usage in sorted(usages, key=lambda each: (each.holder.label, each.order)):
        _use_toolkit_slot(ctx, usage, classes[usage.holder.uml.object_id], shared, slot_names)


def attribute_usages(ctx: Context, holder: Element) -> list[Usage]:
    """The slots of a class's attributes, in position order."""
    ordered = sorted(
        holder.uml.uml_attributes or [], key=lambda each: (each.position or 0, each.attribute_id)
    )
    usages = (_attribute_usage(ctx, holder, attribute) for attribute in ordered)
    return [usage for usage in usages if usage is not None]
