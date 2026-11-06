"""An aggregate survives JSON, RDF and a frame unchanged (PD-27 item 4, PD-12).

``round_trip`` takes an object of a generated aggregate class and checks four things: its JSON,
expanded with the generated context, gives RDF; the RDF, framed with the generated frame and
compacted, gives JSON that builds an equal object; and the RDF of that object is the same graph.

Equal means equal on the public projection: slots annotated ``internal`` never cross the context
(PD-12), so the object is rebuilt from the framed JSON with its own internal values added back,
and the two objects are compared without them. Lists are compared as sets, since RDF keeps no order
among the values of a slot. Nothing here needs ``hypothesis``; the strategies that draw the objects
are in ``rdf_persistence.testkit.strategies``.
"""

import json

from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.formatutils import underscore
from pydantic import BaseModel
from pyld import jsonld
from rdflib import XSD, BNode, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic
from rdflib.term import Node

from rdf_persistence.generation.outputs import FRAME_SUFFIX
from rdf_persistence.services.schema_structure import holds_owned_part, is_internal
from rdf_persistence.testkit.conformance import Conformance

NQUADS = {"format": "application/n-quads"}
NATIVE = {"useNativeTypes": True}
FRAMING_KEYS = {"@context", "@type", "type"}  # the context aliases @type as `type`


def rdf_of(conformance: Conformance, model: BaseModel, class_name: str) -> str:
    """The N-Quads of ``model``, its JSON expanded with the generated context."""
    body = model.model_dump(mode="json", by_alias=True, exclude_none=True)
    node = conformance.jsonld_node(class_name, body)
    nquads: str = jsonld.to_rdf({"@context": conformance.context, **node}, NQUADS)
    return nquads


def dataset_of(graph: Graph) -> dict:
    """The triples of ``graph`` as the dataset ``jsonld.from_rdf`` takes.

    pyld 3.3.0 reads backslash sequences in N-Quads text wrongly (a literal of a backslash and `r`
    comes back as a backslash and a carriage return), so the text goes through rdflib instead.
    """

    def term(node: Node) -> dict:
        if isinstance(node, URIRef):
            return {"type": "IRI", "value": str(node)}
        if isinstance(node, BNode):
            return {"type": "blank node", "value": f"_:{node}"}
        assert isinstance(node, Literal)
        return {"type": "literal", "value": str(node), "datatype": str(node.datatype or XSD.string)}

    triples = [{"subject": term(s), "predicate": term(p), "object": term(o)} for s, p, o in graph]
    return {"@default": triples}


def framed_json(conformance: Conformance, nquads: str, class_name: str) -> dict:
    """The JSON of the aggregate in ``nquads``, framed with the generated frame and compacted."""
    frame = json.loads(
        (conformance.folder / f"{class_name}{FRAME_SUFFIX}").read_text(encoding="utf-8")
    )
    frame["@context"] = conformance.context
    expanded = jsonld.from_rdf(dataset_of(Graph().parse(data=nquads, format="nt")), NATIVE)
    framed: dict = jsonld.frame(expanded, frame)
    return framed


def without_framing(value: object) -> object:
    """``value`` without the context and the type markers the frame adds at every level."""
    if isinstance(value, list):
        return [without_framing(item) for item in value]
    if isinstance(value, dict):
        return {k: without_framing(v) for k, v in value.items() if k not in FRAMING_KEYS}
    return value


def _by_json(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def public_projection(conformance: Conformance, class_name: str, data: dict) -> dict:
    """``data``, the JSON of an object of ``class_name``, without its internal slots and with every list sorted."""
    slots = {underscore(s.name): s for s in conformance.view.class_induced_slots(class_name)}
    return {
        key: _public_value(conformance, slots.get(key), value)
        for key, value in data.items()
        if not (key in slots and is_internal(slots[key]))
    }


def _public_value(conformance: Conformance, slot: SlotDefinition | None, value: object) -> object:
    if isinstance(value, list):
        return sorted((_public_value(conformance, slot, item) for item in value), key=_by_json)
    if slot is not None and holds_owned_part(conformance.view, slot) and isinstance(value, dict):
        return public_projection(conformance, str(slot.range), value)
    return value


def internal_values(conformance: Conformance, class_name: str, data: dict) -> dict:
    """The top-level internal slots of ``data``, which an object needs to be built again."""
    slots = {underscore(s.name): s for s in conformance.view.class_induced_slots(class_name)}
    return {k: v for k, v in data.items() if k in slots and is_internal(slots[k])}


def assert_isomorphic(before: Graph, after: Graph) -> None:
    assert isomorphic(before, after), (
        "the two graphs differ:\n"
        f"only before: {sorted(graph_diff(before, after)[1])}\n"
        f"only after: {sorted(graph_diff(before, after)[2])}"
    )


def round_trip(conformance: Conformance, original: BaseModel, class_name: str) -> None:
    """``original`` goes to RDF and, framed and compacted, back to an equal object and graph.

    Raises:
        AssertionError: When the objects differ on their public projection or the graphs differ.
    """
    nquads = rdf_of(conformance, original, class_name)
    body = original.model_dump(mode="json", by_alias=True, exclude_none=True)
    framed = without_framing(framed_json(conformance, nquads, class_name))
    assert isinstance(framed, dict), "a framed aggregate is one object"
    back = conformance.models[class_name].model_validate(
        {**framed, **internal_values(conformance, class_name, body)}
    )
    back_body = back.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert public_projection(conformance, class_name, back_body) == public_projection(
        conformance, class_name, body
    ), "the objects differ after the round trip"
    assert_isomorphic(
        Graph().parse(data=nquads, format="nt"),
        Graph().parse(data=rdf_of(conformance, back, class_name), format="nt"),
    )
