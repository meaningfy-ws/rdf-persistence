"""What a schema says about its aggregates and its declared rules, in one place (PD-22).

The annotations the toolkit reads (typed by the generated ``RpAnnotation``), the application's own
modules, aggregate roots, owned and internal slots, the defaults of PD-11, and the two rules the
generated classes and the generated shapes both enforce: the presence alternatives of a class
(``exactly_one_of``, ``any_of``) and the keyed slots (``unique_keys``). Needs only ``linkml-runtime``,
so the mapper and the freshness check can use it without the ``generate`` extra.
"""

from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Any

from linkml_runtime.linkml_model.meta import (
    AnonymousClassExpression,
    ClassDefinition,
    PresenceEnum,
    SchemaDefinition,
    SlotDefinition,
    UniqueKey,
)
from linkml_runtime.utils.formatutils import underscore
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import XSD, Graph, Literal, URIRef
from rdflib.term import Node

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.generated.rp_core import DatabaseKind, GraphKind, RpAnnotation
from rdf_persistence.services.schema import PACKAGE_DIR, load_schema

AGGREGATE_ROOT = "AggregateRoot"
TENANT_ACCESS = "TenantAccess"
DESCRIPTION = "description"
LABEL = "label"
EXACTLY_ONE_OF = "exactly_one_of"
ANY_OF = "any_of"
PRESENT = PresenceEnum(PresenceEnum.PRESENT)
ABSENT = PresenceEnum(PresenceEnum.ABSENT)
_TRUE = "true"
URI_TYPES = frozenset({"uri", "uriorcurie"})
_SUPPORTED_CONDITION_FIELDS = {"name", "required", "value_presence"}

# One alternative of a presence rule: each named slot present or absent, all of them together.
Alternative = list[tuple[str, PresenceEnum]]


class UnsupportedRuleError(ValueError):
    """A rule the schema declares in a form that the generated classes and shapes cannot enforce."""


def annotation_text(element: object, tag: Enum) -> str | None:
    """The value of the element's annotation ``tag`` (a member of a generated annotation enum) as written; None when it has none."""
    annotations = getattr(element, "annotations", None) or {}
    # a class read from the schema holds a dict, an induced slot a JsonObj
    found = (
        annotations.get(tag.value)
        if isinstance(annotations, dict)
        else getattr(annotations, tag.value, None)
    )
    return None if found is None else str(found.value)


def annotation(element: object, tag: RpAnnotation) -> str | None:
    """The lower-cased value of the element's annotation ``tag``; None when it has none."""
    text = annotation_text(element, tag)
    return None if text is None else text.lower()


def flag(element: object, tag: RpAnnotation) -> bool:
    """True when the element's annotation ``tag`` is ``true``."""
    return annotation(element, tag) == _TRUE


def is_owned(slot: object) -> bool:
    return flag(slot, RpAnnotation.OWNED)


def json_name(slot: SlotDefinition) -> str:
    """The key of the slot in a JSON body: its alias, else its name, in snake case. The context uses it too."""
    return str(underscore(slot.alias or slot.name))


def holds_owned_part(view: SchemaView, slot: SlotDefinition) -> bool:
    """True when the values of the slot are objects the aggregate owns, written as nodes of its graph."""
    return slot.range in view.all_classes() and is_owned(slot)


def holds_iri(view: SchemaView, slot: SlotDefinition) -> bool:
    """True when the values of the slot are IRIs: a reference to another aggregate, or a ``uri`` slot."""
    if slot.range in view.all_classes():
        return not is_owned(slot)
    return bool(URI_TYPES & set(view.type_ancestors(slot.range)))


def rdf_term(view: SchemaView, slot: SlotDefinition, value: Any) -> URIRef | Literal:
    """``value``, of a slot that holds no owned part, as the RDF term the store keeps it as.

    An enum value is its permissible value's meaning IRI, or a literal of its text when it has none;
    a reference to another aggregate and a ``uri`` are IRIs; any other value is a literal of the
    datatype of the slot's type, a plain literal for a string. The mapper writes values and the
    listings match them through this one rule.

    Raises:
        ValueError: ``value`` is not a permissible value of the slot's enum.
    """
    range_ = slot.range or str(view.schema.default_range)
    if range_ in view.all_enums():
        text = str(value)
        permissible = view.get_enum(range_).permissible_values.get(text)
        if permissible is None:
            raise ValueError(f"{text!r} is not a value of {range_}")
        meaning = permissible.meaning
        return URIRef(view.expand_curie(str(meaning))) if meaning else Literal(text)
    if holds_iri(view, slot):
        return URIRef(str(value))
    datatype = URIRef(view.expand_curie(str(view.get_type(range_).uri)))
    return Literal(str(value)) if datatype == XSD.string else Literal(value, datatype=datatype)


def is_internal(slot: object) -> bool:
    return flag(slot, RpAnnotation.INTERNAL)


def internal_predicates(
    view: SchemaView,
) -> dict[Node, str]:  # Node: rdflib types a graph's predicates so
    """The predicate of every ``internal`` slot of the schema, with the JSON name of the slot."""
    return {
        URIRef(view.get_uri(slot, expand=True)): json_name(slot)
        for name in view.all_classes()
        for slot in view.class_induced_slots(name)
        if is_internal(slot)
    }


def refuse_internal(graph: Graph, internal: dict[Node, str]) -> None:
    """Raise ``InvalidBody`` when ``graph`` gives an ``internal`` slot a value: only the service sets those."""
    for predicate in set(graph.predicates()):
        if predicate in internal:
            raise InvalidBody(f"{internal[predicate]} is set by the service")


def is_bookkeeping(slot: object) -> bool:
    """True for a slot the session writes about a graph, which closed shapes ignore."""
    return flag(slot, RpAnnotation.BOOKKEEPING)


def is_unlabelled(cls: object) -> bool:
    return flag(cls, RpAnnotation.RP_UNLABELLED)


def is_tenant_root(cls: ClassDefinition) -> bool:
    """The tenant's root object lives in the meta graph and needs no path (PD-8)."""
    return annotation(cls, RpAnnotation.GRAPH) == GraphKind.META.value


def is_toolkit_schema(folder: Path) -> bool:
    """True for the toolkit's own schemas, which PD-23 exempts from the class-level rules."""
    return folder.resolve().is_relative_to(PACKAGE_DIR)


def own_schemas(view: SchemaView, folder: Path) -> list[SchemaDefinition]:
    """The modules of the closure kept in ``folder``, beside the root schema (not the metamodel's)."""
    view.imports_closure()
    return [
        schema
        for schema in view.schema_map.values()
        if schema.source_file and Path(schema.source_file).resolve().parent == folder.resolve()
    ]


def own_classes(schemas: list[SchemaDefinition]) -> list[ClassDefinition]:
    return [cls for schema in schemas for cls in schema.classes.values()]


def declared_slot_names(cls: ClassDefinition) -> list[str]:
    """The slots a class declares or narrows itself, in declaration order, as opposed to inherited ones."""
    return list(dict.fromkeys([*cls.slots, *cls.attributes, *cls.slot_usage]))


def declared_slots(cls: ClassDefinition) -> set[str]:
    """The slots a class declares or narrows itself, as opposed to the ones it inherits."""
    return set(declared_slot_names(cls))


def aggregate_roots(view: SchemaView, classes: list[ClassDefinition]) -> list[ClassDefinition]:
    """The concrete classes whose induced ancestors include ``AggregateRoot``."""
    return [
        cls
        for cls in classes
        if not cls.mixin and not cls.abstract and AGGREGATE_ROOT in view.class_ancestors(cls.name)
    ]


def root_classes(view: SchemaView, folder: Path) -> list[ClassDefinition]:
    """The aggregate roots and the tenant root of the modules kept in ``folder``, in schema order."""
    classes = own_classes(own_schemas(view, folder))
    roots = {root.name for root in aggregate_roots(view, classes)}
    return [cls for cls in classes if cls.name in roots or is_tenant_root(cls)]


def served_roots(view: SchemaView) -> list[ClassDefinition]:
    """The aggregate roots with a path that live in the tenant databases: what the generic router serves.

    The tenant's access record lives in the system database and has its own routes, so it is left out.
    """
    roots = aggregate_roots(view, list(view.all_classes().values()))
    return [
        root
        for root in roots
        if annotation(root, RpAnnotation.DATABASE) != DatabaseKind.SYSTEM.value
        and annotation_text(root, RpAnnotation.RP_PATH)
    ]


def _only(found: list[ClassDefinition], what: str) -> ClassDefinition:
    if len(found) != 1:
        raise LookupError(f"the schema must define exactly one {what}, found {len(found)}")
    return found[0]


def tenant_root_class(view: SchemaView) -> ClassDefinition:
    """The class of the tenant's root object, the one annotated ``graph: meta``.

    Raises:
        LookupError: The schema has none or several.
    """
    return _only([c for c in view.all_classes().values() if is_tenant_root(c)], "tenant root class")


def tenant_access_class(view: SchemaView) -> ClassDefinition:
    """The application's access record class: the one concrete descendant of ``TenantAccess``.

    Raises:
        LookupError: The schema has none or several.
    """
    found = [
        c
        for c in view.all_classes().values()
        if not c.abstract and not c.mixin and TENANT_ACCESS in view.class_ancestors(c.name)
    ]
    return _only([c for c in found if c.name != TENANT_ACCESS] or found, "tenant access class")


def owned_slots(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[tuple[str, str]]:
    """``(slot, range)`` of each declared slot marked ``owned: true`` whose range is a class."""
    for cls in classes:
        induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
        for name in sorted(declared_slots(cls) & induced.keys()):
            slot = induced[name]
            if is_owned(slot) and slot.range in view.all_classes():
                yield name, slot.range


def owned_classes(view: SchemaView, classes: list[ClassDefinition]) -> set[str]:
    """The classes reached through ``owned`` slots, with their subclasses."""
    return {
        owned
        for _, range_ in owned_slots(view, classes)
        for owned in view.class_descendants(range_)
    }


def owned_class_names(view: SchemaView, folder: Path) -> set[str]:
    """The classes the modules kept in ``folder`` reach through ``owned`` slots."""
    return owned_classes(view, own_classes(own_schemas(view, folder)))


def inherits_from_metamodel(view: SchemaView, cls: ClassDefinition, own: set[str]) -> bool:
    """True when an ``is_a`` ancestor of ``cls`` is not the application's own (PD-23 exempts it)."""
    return any(name not in own for name in view.class_ancestors(cls.name, mixins=False)[1:])


def _set_required(cls: ClassDefinition, slot: str, required: bool) -> None:
    usage = cls.slot_usage.get(slot) or SlotDefinition(name=slot)
    usage.required = required
    cls.slot_usage[slot] = usage


def apply_defaults(view: SchemaView, folder: Path) -> None:
    """Make an unlabelled class's label optional and every aggregate root's description required (PD-11).

    Only the application's classes change; the toolkit's own schemas are left as they are (PD-23).
    """
    if is_toolkit_schema(folder):
        return
    classes = own_classes(own_schemas(view, folder))
    for cls in classes:
        if is_unlabelled(cls):  # Described gives it the label slot
            _set_required(cls, LABEL, False)
    for root in aggregate_roots(view, classes):
        _set_required(root, DESCRIPTION, True)
    view.set_modified()


def generation_view(path: str | Path) -> SchemaView:
    """The schema at ``path`` as the generators see it: loaded, with the defaults of PD-11 applied."""
    view = load_schema(path)
    apply_defaults(view, Path(path).parent)
    return view


def _condition_presence(where: str, condition: SlotDefinition) -> PresenceEnum:
    """Whether a slot condition says the slot is present or absent; anything else is refused."""
    others = {
        k for k, v in vars(condition).items() if v not in (None, [], {})
    } - _SUPPORTED_CONDITION_FIELDS
    if others:
        raise UnsupportedRuleError(
            f"{where} uses {sorted(others)}; only required and value_presence are supported"
        )
    if condition.required is False:
        raise UnsupportedRuleError(f"{where} has required: false; use value_presence: ABSENT")
    states = {PRESENT} if condition.required else set()
    if condition.value_presence is not None:
        states.add(PRESENT if str(condition.value_presence) == str(PRESENT) else ABSENT)
    if len(states) != 1:
        raise UnsupportedRuleError(
            f"{where} must state exactly one of required: true and value_presence"
        )
    return states.pop()


def _alternative(
    rule: str, cls: ClassDefinition, expression: AnonymousClassExpression, slots: set[str]
) -> Alternative:
    extra = {k for k, v in vars(expression).items() if v not in (None, [], {})} - {
        "slot_conditions"
    }
    if extra or not expression.slot_conditions:
        raise UnsupportedRuleError(
            f"{cls.name}: {rule}: an alternative must hold slot_conditions only, found {sorted(extra) or 'none'}"
        )
    alternative: Alternative = []
    for slot, condition in expression.slot_conditions.items():
        if slot not in slots:
            raise UnsupportedRuleError(
                f"{cls.name}: {rule}: slot {slot} is not a slot of the class"
            )
        where = f"{cls.name}: {rule}: slot condition on {slot}"
        alternative.append((slot, _condition_presence(where, condition)))
    return alternative


def presence_alternatives(view: SchemaView, cls: ClassDefinition, rule: str) -> list[Alternative]:
    """The alternatives of the ``rule`` (``EXACTLY_ONE_OF`` or ``ANY_OF``) that ``cls`` declares itself.

    Each alternative lists its slots, each ``PRESENT`` or ``ABSENT``. A condition that says anything
    else raises ``UnsupportedRuleError``, so the classes and the shapes refuse the same schemas.
    """
    slots = {slot.name for slot in view.class_induced_slots(cls.name)}
    return [_alternative(rule, cls, expression, slots) for expression in getattr(cls, rule) or []]


def _holds_objects(view: SchemaView, slot: SlotDefinition) -> bool:
    """True when the values of a slot ranging over a class are objects, not references by identifier."""
    return bool(
        slot.inlined or slot.inlined_as_list or view.get_identifier_slot(slot.range) is None
    )


def _keys_of(view: SchemaView, range_: str) -> dict[str, UniqueKey]:
    """The unique keys of a class and its ancestors by name; the nearest declaration of a name wins."""
    keys: dict[str, UniqueKey] = {}
    for name in view.class_ancestors(range_):
        for key_name, key in (view.get_class(name).unique_keys or {}).items():
            keys.setdefault(key_name, key)
    return keys


def keyed_slots(view: SchemaView, cls: ClassDefinition) -> list[tuple[SlotDefinition, UniqueKey]]:
    """``(slot, key)`` of each multivalued slot of ``cls`` holding objects whose class declares a key.

    The slots are those the class has, inherited ones too, by name; a reference to another aggregate
    (values given by identifier) holds no objects and is left out. The range's key of a name is
    the one nearest to it in its ancestry.
    """
    classes = view.all_classes()
    slots = sorted(view.class_induced_slots(cls.name), key=lambda slot: str(slot.name))
    return [
        (slot, key)
        for slot in slots
        if slot.multivalued and slot.range in classes and _holds_objects(view, slot)
        for key in _keys_of(view, slot.range).values()
    ]
