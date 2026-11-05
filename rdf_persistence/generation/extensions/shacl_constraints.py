"""Shape constraints for the rules the stock gen-shacl ignores (PD-24).

``exactly_one_of`` becomes ``sh:xone`` and ``any_of`` becomes ``sh:or``, on the shape of every concrete
class that declares the rule or inherits it. ``unique_keys`` becomes a SPARQL constraint on the shape
of the class that owns the multivalued slot whose range declares the key; two items refuse each other
when every key slot has the same value, and an absent value equals an absent value, as in the pydantic
validators.

Only a slot condition that says a slot is required (``required: true``, ``value_presence: PRESENT``) or
absent (``value_presence: ABSENT``) is supported; anything else raises rather than being dropped.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from linkml_runtime.linkml_model.meta import (
    AnonymousClassExpression,
    ClassDefinition,
    PresenceEnum,
    SlotDefinition,
    UniqueKey,
)
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, SH
from rdflib.term import Node

PRESENT = PresenceEnum(PresenceEnum.PRESENT)
ABSENT = PresenceEnum(PresenceEnum.ABSENT)


@dataclass(frozen=True)
class UniqueKeyOn:
    """A unique key that a class's multivalued slot is subject to, with the URIs the query needs."""

    slot: str
    path: URIRef
    key: str
    description: str | None
    key_paths: tuple[URIRef, ...]


def shape_uri(sv: SchemaView, cls: ClassDefinition) -> URIRef:
    """The IRI of the class's shape: its native IRI, so classes sharing a ``class_uri`` stay apart."""
    return URIRef(sv.get_uri(cls, expand=True, native=True))


def _path(sv: SchemaView, slot: SlotDefinition) -> URIRef:
    return URIRef(sv.get_uri(slot, expand=True))


def _concrete(sv: SchemaView) -> Iterator[ClassDefinition]:
    return (c for c in sv.all_classes().values() if not (c.mixin or c.abstract))


def _expressions(
    sv: SchemaView, cls: ClassDefinition, rule: str
) -> Iterator[list[AnonymousClassExpression]]:
    """The alternatives of every ``rule`` (``exactly_one_of`` or ``any_of``) of ``cls`` and its ancestors."""
    for name in sv.class_ancestors(cls.name):
        alternatives = getattr(sv.get_class(name), rule)
        if alternatives:
            yield list(alternatives)


def _alternative(
    sv: SchemaView, cls: ClassDefinition, expression: AnonymousClassExpression
) -> tuple[BNode, Graph]:
    """A node shape that holds when the expression's slot conditions hold."""
    node = BNode()
    g = Graph()
    for name, condition in expression.slot_conditions.items():
        slot = sv.induced_slot(name, cls.name)
        prop = BNode()
        g.add((node, SH.property, prop))
        g.add((prop, SH.path, _path(sv, slot)))
        if condition.value_presence == ABSENT:
            g.add((prop, SH.maxCount, Literal(0)))
        elif condition.required or condition.value_presence == PRESENT:
            g.add((prop, SH.minCount, Literal(1)))
        else:
            raise ValueError(f"{cls.name}: the condition on {name} is not required or present")
    return node, g


def _choice(
    g: Graph, sv: SchemaView, cls: ClassDefinition, shape: URIRef, rule: str, kind: URIRef
) -> None:
    for alternatives in _expressions(sv, cls, rule):
        nodes: list[Node] = []
        for expression in alternatives:
            node, part = _alternative(sv, cls, expression)
            g += part
            nodes.append(node)
        head = BNode()
        Collection(g, head, nodes)
        g.add((shape, kind, head))


def _unique_keys(sv: SchemaView, range_: str) -> Iterator[tuple[str, UniqueKey]]:
    for name in sv.class_ancestors(range_):
        yield from sv.get_class(name).unique_keys.items()


def keys_on(sv: SchemaView, cls: ClassDefinition) -> Iterator[UniqueKeyOn]:
    """The unique keys the multivalued class-ranged slots of ``cls`` are subject to."""
    classes = sv.all_classes()
    for slot in sv.class_induced_slots(cls.name):
        if not (slot.multivalued and slot.range in classes):
            continue
        for key_name, key in _unique_keys(sv, slot.range):
            key_paths = tuple(
                _path(sv, sv.induced_slot(k, slot.range)) for k in key.unique_key_slots
            )
            yield UniqueKeyOn(slot.name, _path(sv, slot), key_name, key.description, key_paths)


def unique_key_query(on: UniqueKeyOn) -> str:
    """A SELECT that returns the focus node when two values of the slot have equal key values."""
    lines = [
        "SELECT DISTINCT $this",
        "WHERE {",
        f"  $this <{on.path}> ?first .",
        f"  $this <{on.path}> ?second .",
        "  FILTER (!sameTerm(?first, ?second))",
    ]
    for index, path in enumerate(on.key_paths):
        lines += [
            f"  OPTIONAL {{ ?first <{path}> ?first_{index} . }}",
            f"  OPTIONAL {{ ?second <{path}> ?second_{index} . }}",
            f"  FILTER ((!bound(?first_{index}) && !bound(?second_{index}))"
            f" || sameTerm(?first_{index}, ?second_{index}))",
        ]
    return "\n".join([*lines, "}"])


def _unique(g: Graph, sv: SchemaView, cls: ClassDefinition, shape: URIRef) -> None:
    for on in keys_on(sv, cls):
        constraint = BNode()
        message = on.description or f"two values of {on.slot} share the key {on.key}"
        g.add((shape, SH.sparql, constraint))
        g.add((constraint, RDF.type, SH.SPARQLConstraint))
        g.add((constraint, SH.message, Literal(f"{cls.name}.{on.slot}: {message}")))
        g.add((constraint, SH.select, Literal(unique_key_query(on))))


def constraints_graph(sv: SchemaView, classes: Iterable[ClassDefinition] | None = None) -> Graph:
    """The triples that add the rules to the shapes of ``classes`` (default: every concrete class)."""
    g = Graph()
    for cls in classes if classes is not None else _concrete(sv):
        shape = shape_uri(sv, cls)
        _choice(g, sv, cls, shape, "exactly_one_of", SH.xone)
        _choice(g, sv, cls, shape, "any_of", SH["or"])
        _unique(g, sv, cls, shape)
    return g
