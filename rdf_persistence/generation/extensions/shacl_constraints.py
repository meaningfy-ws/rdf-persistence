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

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, SH
from rdflib.term import Node

from rdf_persistence.generation.exceptions import (
    SchemaGenerationError,
    refusing_unsupported_rules,
)
from rdf_persistence.generation.generated.rp_generation import UniqueKeyOn
from rdf_persistence.services.schema_structure import (
    ABSENT,
    ANY_OF,
    EXACTLY_ONE_OF,
    Alternative,
    keyed_slots,
    presence_alternatives,
)


def shape_uri(sv: SchemaView, cls: ClassDefinition) -> URIRef:
    """The IRI of the class's shape: its native IRI, so classes sharing a ``class_uri`` stay apart."""
    return URIRef(sv.get_uri(cls, expand=True, native=True))


def _path(sv: SchemaView, slot: SlotDefinition) -> URIRef:
    return URIRef(sv.get_uri(slot, expand=True))


def _concrete(sv: SchemaView) -> Iterator[ClassDefinition]:
    return (c for c in sv.all_classes().values() if not (c.mixin or c.abstract))


def _declared(sv: SchemaView, cls: ClassDefinition, rule: str) -> Iterator[list[Alternative]]:
    """The alternatives of every ``rule`` of ``cls`` and its ancestors."""
    for name in sv.class_ancestors(cls.name):
        with refusing_unsupported_rules():
            alternatives = presence_alternatives(sv, sv.get_class(name), rule)
        if alternatives:
            yield alternatives


def _alternative(
    sv: SchemaView, cls: ClassDefinition, alternative: Alternative
) -> tuple[BNode, Graph]:
    """A node shape that holds when the alternative's slots are present or absent as it says."""
    node = BNode()
    g = Graph()
    for name, presence in alternative:
        prop = BNode()
        g.add((node, SH.property, prop))
        g.add((prop, SH.path, _path(sv, sv.induced_slot(name, cls.name))))
        g.add(
            (
                prop,
                SH.maxCount if presence == ABSENT else SH.minCount,
                Literal(0 if presence == ABSENT else 1),
            )
        )
    return node, g


def _choice(
    g: Graph, sv: SchemaView, cls: ClassDefinition, shape: URIRef, rule: str, kind: URIRef
) -> None:
    for alternatives in _declared(sv, cls, rule):
        nodes: list[Node] = []
        for alternative in alternatives:
            node, part = _alternative(sv, cls, alternative)
            g += part
            nodes.append(node)
        head = BNode()
        Collection(g, head, nodes)
        g.add((shape, kind, head))


def keys_on(sv: SchemaView, cls: ClassDefinition) -> Iterator[UniqueKeyOn]:
    """The unique keys the multivalued class-ranged slots of ``cls`` are subject to."""
    for slot, key in keyed_slots(sv, cls):
        key_paths = [_path(sv, sv.induced_slot(k, slot.range)) for k in key.unique_key_slots]
        yield UniqueKeyOn(
            name=slot.name,
            slot_iri=str(_path(sv, slot)),
            key_name=key.unique_key_name,
            description=key.description,
            key_iris=[str(path) for path in key_paths],
        )


def _iri(iri: str) -> str:
    """``iri`` as ``<...>`` for a query; refused when it holds a character that could end the IRI early."""
    try:
        return str(URIRef(iri).n3())
    except Exception as error:  # rdflib raises a bare Exception for an IRI it cannot serialize
        raise SchemaGenerationError(f"{iri}: not an IRI that can go into a query") from error


def unique_key_query(on: UniqueKeyOn) -> str:
    """A SELECT that returns the focus node when two values of the slot have equal key values.

    The IRIs go through ``URIRef.n3()``, which refuses one that could break out of ``<...>``.
    """
    lines = [
        "SELECT DISTINCT $this",
        "WHERE {",
        f"  $this {_iri(on.slot_iri)} ?first .",
        f"  $this {_iri(on.slot_iri)} ?second .",
        "  FILTER (!sameTerm(?first, ?second))",
    ]
    for index, path in enumerate(on.key_iris):
        lines += [
            f"  OPTIONAL {{ ?first {_iri(path)} ?first_{index} . }}",
            f"  OPTIONAL {{ ?second {_iri(path)} ?second_{index} . }}",
            f"  FILTER ((!bound(?first_{index}) && !bound(?second_{index}))"
            f" || sameTerm(?first_{index}, ?second_{index}))",
        ]
    return "\n".join([*lines, "}"])


def _unique(g: Graph, sv: SchemaView, cls: ClassDefinition, shape: URIRef) -> None:
    for on in keys_on(sv, cls):
        constraint = BNode()
        message = on.description or f"two values of {on.name} share the key {on.key_name}"
        g.add((shape, SH.sparql, constraint))
        g.add((constraint, RDF.type, SH.SPARQLConstraint))
        g.add((constraint, SH.message, Literal(f"{cls.name}.{on.name}: {message}")))
        g.add((constraint, SH.select, Literal(unique_key_query(on))))


def constraints_graph(sv: SchemaView, classes: Iterable[ClassDefinition] | None = None) -> Graph:
    """The triples that add the rules to the shapes of ``classes`` (default: every concrete class)."""
    g = Graph()
    for cls in classes if classes is not None else _concrete(sv):
        shape = shape_uri(sv, cls)
        _choice(g, sv, cls, shape, EXACTLY_ONE_OF, SH.xone)
        _choice(g, sv, cls, shape, ANY_OF, SH["or"])
        _unique(g, sv, cls, shape)
    return g
