"""An aggregate survives JSON, RDF and a frame unchanged (PD-27 item 4, PD-12).

``round_trip`` takes an object of a generated aggregate class and checks four things: its JSON,
expanded with the generated context, gives RDF; the RDF, framed with the generated frame and
compacted, gives JSON that builds an equal object; and the RDF of that object is the same graph.
Expanding and framing are the router's own (``Documents.expand`` and ``Documents.frame``).

Equal means equal on the public projection: slots annotated ``internal`` never cross the context
(PD-12), so the object is rebuilt from the framed JSON with its own internal values added back,
and the two objects are compared without them. Lists are compared as sets, since RDF keeps no order
among the values of a slot. Nothing here needs ``hypothesis``; the strategies that draw the objects
are in ``rdf_persistence.testkit.strategies``.
"""

import json

from pydantic import BaseModel
from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence.services.artifacts import CONTEXT_KEY, TYPE_KEY
from rdf_persistence.services.schema_structure import is_internal
from rdf_persistence.testkit.conformance import Conformance

FRAMING_KEYS = {CONTEXT_KEY, TYPE_KEY, "type"}  # the context aliases @type as `type`


def without_framing(value: object) -> object:
    """``value`` without the context and the type markers the frame adds at every level."""
    if isinstance(value, list):
        return [without_framing(item) for item in value]
    if isinstance(value, dict):
        return {k: without_framing(v) for k, v in value.items() if k not in FRAMING_KEYS}
    return value


def _sorted(value: object) -> object:
    """``value`` with every list sorted, since RDF keeps no order among the values of a slot."""
    if isinstance(value, list):
        return sorted(
            (_sorted(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True)
        )
    if isinstance(value, dict):
        return {key: _sorted(item) for key, item in value.items()}
    return value


def public_projection(conformance: Conformance, class_name: str, data: dict) -> object:
    """``data``, the JSON of an object of ``class_name``, without its internal slots and with every list sorted."""
    return _sorted(conformance.public(class_name, data))


def internal_values(conformance: Conformance, class_name: str, data: dict) -> dict:
    """The top-level internal slots of ``data``, which an object needs to be built again."""
    slots = conformance.slots_of(class_name)
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
    graph = conformance.graph_of(original, class_name)
    body = original.model_dump(mode="json", by_alias=True, exclude_none=True)
    cls = conformance.view.get_class(class_name)
    framed = without_framing(conformance.documents.frame(graph, cls))
    assert isinstance(framed, dict), "a framed aggregate is one object"
    back = conformance.models[class_name].model_validate(
        {**framed, **internal_values(conformance, class_name, body)}
    )
    back_body = back.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert public_projection(conformance, class_name, back_body) == public_projection(
        conformance, class_name, body
    ), "the objects differ after the round trip"
    assert_isomorphic(graph, conformance.graph_of(back, class_name))
