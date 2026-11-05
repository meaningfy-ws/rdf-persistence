"""An aggregate survives JSON, RDF and a frame unchanged (PD-27 item 4, PD-12)."""

import json
import os
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import BaseModel
from pyld import jsonld
from rdflib import XSD, BNode, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic
from rdflib.term import Node

from rdf_persistence.testkit.conformance import Conformance
from tests.unit.generation.strategies import IRI_BASE, aggregate

TOY_FOLDER = Path(__file__).parents[2] / "fixtures" / "library"
AGGREGATES = ["Book", "Scan", "Library"]
NQUADS = {"format": "application/n-quads"}
NATIVE = {"useNativeTypes": True}
FRAMING_KEYS = {"@context", "@type", "type"}  # the context aliases @type as `type`

# CI runs the same examples every time (checklist 8); locally Hypothesis explores.
settings.register_profile(
    "ci", derandomize=True, max_examples=20, deadline=None, suppress_health_check=list(HealthCheck)
)
settings.register_profile(
    "default", max_examples=40, deadline=None, suppress_health_check=list(HealthCheck)
)
settings.load_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "ci" if os.environ.get("CI") else "default")
)


def rdf_of(toy: Conformance, model: BaseModel, class_name: str) -> str:
    """The N-Quads of ``model``, its JSON expanded with the generated context."""
    body = model.model_dump(mode="json", by_alias=True, exclude_none=True)
    node = toy.jsonld_node(class_name, body)
    nquads: str = jsonld.to_rdf({"@context": toy.context, **node}, NQUADS)
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


def framed_json(toy: Conformance, nquads: str, class_name: str) -> dict:
    """The JSON of the aggregate in ``nquads``, framed with the generated frame and compacted."""
    frame = json.loads((TOY_FOLDER / "generated" / f"{class_name}.frame.jsonld").read_text())
    frame["@context"] = toy.context
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


def unordered(model: BaseModel) -> object:
    """The JSON of ``model`` with every list sorted: RDF keeps no order among the values of a slot."""

    def sort(value: object) -> object:
        if isinstance(value, list):
            return sorted(
                (sort(item) for item in value), key=lambda v: json.dumps(v, sort_keys=True)
            )
        if isinstance(value, dict):
            return {k: sort(v) for k, v in value.items()}
        return value

    return sort(model.model_dump(mode="json", by_alias=True))


def assert_isomorphic(before: Graph, after: Graph) -> None:
    assert isomorphic(before, after), (
        "the two graphs differ:\n"
        f"only before: {sorted(graph_diff(before, after)[1])}\n"
        f"only after: {sorted(graph_diff(before, after)[2])}"
    )


def toy_library() -> Conformance:
    """The toy library's schema and generated artefacts (loaded once; not a fixture, so that
    Hypothesis does not print it into a failure's repr)."""
    return Conformance.of(TOY_FOLDER / "library.yaml")


def assert_survives(toy: Conformance, original: BaseModel, class_name: str) -> None:
    """``original`` goes to RDF and, framed and compacted, back to an equal object and graph."""
    nquads = rdf_of(toy, original, class_name)

    back = toy.models[class_name].model_validate(
        without_framing(framed_json(toy, nquads, class_name))
    )

    assert unordered(back) == unordered(original), "the objects differ after the round trip"
    assert_isomorphic(
        Graph().parse(data=nquads, format="nt"),
        Graph().parse(data=rdf_of(toy, back, class_name), format="nt"),
    )


@pytest.mark.parametrize("class_name", AGGREGATES)
@given(data=st.data())
def test_an_aggregate_survives_json_rdf_and_a_frame(class_name: str, data: st.DataObject) -> None:
    toy = toy_library()
    assert_survives(toy, data.draw(aggregate(toy, class_name)), class_name)


def test_a_backslash_followed_by_r_in_text_is_not_read_as_a_carriage_return() -> None:
    toy = toy_library()
    book = toy.models["Book"].model_validate(
        {"id": f"{IRI_BASE}1", "label": "Dune", "description": "\\r"}
    )
    assert_survives(toy, book, "Book")
