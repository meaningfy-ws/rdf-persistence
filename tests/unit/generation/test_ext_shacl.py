"""Golden test and behaviour of the gen-shacl extension (PD-7, PD-24, PD-25)."""

from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, RDF, SH

from rdf_persistence.generation.extensions.shacl import render
from rdf_persistence.generation.steps import SHAPES_STEP

from .golden import assert_matches_toy, run_toy

RP = "https://meaningfy.ws/ns/rdf-persistence#"
BOOKKEEPING = {
    URIRef(f"{RP}version"),
    DCTERMS.created,
    DCTERMS.modified,
    DCTERMS.creator,
    DCTERMS.contributor,
}
LIB = "https://example.org/ns/library#"


@pytest.fixture(scope="module")
def shapes(generated_toy: Path) -> Graph:
    return Graph().parse(generated_toy / "shapes.ttl")


def ignored(shapes: Graph, shape: str) -> set[URIRef]:
    node = shapes.value(URIRef(shape), SH.ignoredProperties)
    return set(Collection(shapes, node))  # type: ignore[arg-type]


def test_the_toy_shapes_equal_the_committed_tree(tmp_path: Path) -> None:
    assert_matches_toy(run_toy(SHAPES_STEP, tmp_path), "generated/shapes.ttl")


def test_shapes_are_written_next_to_the_python_output(generated_toy: Path) -> None:
    assert (generated_toy / "library.py").is_file(), "the Python output sits in the same folder"
    assert (generated_toy / "shapes.ttl").is_file(), "the shapes sit next to the Python output"


@pytest.mark.parametrize("shape", ["Chapter", "Book", "Library", "LibraryAccess"])
def test_a_closed_shape_ignores_the_bookkeeping_predicates(shapes: Graph, shape: str) -> None:
    assert ignored(shapes, f"{LIB}{shape}") >= BOOKKEEPING, f"{shape} must ignore the bookkeeping"


def test_the_ignored_list_keeps_the_type_predicate(shapes: Graph) -> None:
    assert RDF.type in ignored(shapes, f"{LIB}Chapter"), "rdf:type must stay ignored"


def test_a_mixin_shape_is_left_open_and_without_bookkeeping(shapes: Graph) -> None:
    mixin = URIRef(f"{RP}AggregateRoot")
    assert not BOOKKEEPING & ignored(shapes, str(mixin)), "an open shape needs no ignored list"


SHARED = """
id: https://example.org/ns/shared
name: shared
title: Shared
description: Two classes sharing one class_uri.
prefixes: {s: "https://example.org/ns/s#", linkml: "https://w3id.org/linkml/"}
default_prefix: s
default_range: string
imports: [linkml:types]
classes:
  Base:
    title: Base
    description: A base class.
    class_uri: s:Thing
  Narrow:
    title: Narrow
    description: A subclass with the same class_uri.
    is_a: Base
    class_uri: s:Thing
"""


def test_two_classes_sharing_a_class_uri_get_two_shapes(tmp_path: Path) -> None:
    path = tmp_path / "shared.yaml"
    path.write_text(SHARED, encoding="utf-8")
    graph = Graph().parse(data=render(path)[0].text, format="turtle")
    thing = URIRef("https://example.org/ns/s#Thing")
    expected = {URIRef("https://example.org/ns/s#Base"), URIRef("https://example.org/ns/s#Narrow")}
    assert set(graph.subjects(SH.targetClass, thing)) == expected, (
        "each class needs a shape of its own"
    )


def test_a_slot_that_refers_to_another_aggregate_is_not_checked_for_a_class(shapes: Graph) -> None:
    path = URIRef("http://schema.org/exampleOfWork")
    prop = next(
        p for p in shapes.objects(URIRef(f"{LIB}Scan"), SH.property) if (p, SH.path, path) in shapes
    )
    assert (prop, SH.node, None) not in shapes, "a reference must not require the target's triples"
    assert (prop, SH["class"], None) not in shapes, "a reference must not require the target's type"
    assert (prop, SH.nodeKind, SH.IRI) in shapes, "a reference is still an IRI"


def test_an_owned_part_is_checked_against_its_own_shape(shapes: Graph) -> None:
    path = URIRef(f"{LIB}chapter")
    prop = next(
        p for p in shapes.objects(URIRef(f"{LIB}Book"), SH.property) if (p, SH.path, path) in shapes
    )
    assert (prop, SH.node, URIRef(f"{LIB}Chapter")) in shapes, (
        "an owned part must conform to its shape"
    )


IDENTIFIED = """
id: https://example.org/ns/identified
name: identified
title: Identified
description: One class with an identifier and one without.
prefixes: {s: "https://example.org/ns/s#", linkml: "https://w3id.org/linkml/"}
default_prefix: s
default_range: string
imports: [linkml:types]
classes:
  Named:
    title: Named
    description: An object identified by its IRI.
    slots: [id, note, hidden]
  Anonymous:
    title: Anonymous
    description: An object that has no identifier, a blank node.
    slots: [note]
slots:
  id:
    title: Identifier
    description: The IRI.
    range: uri
    identifier: true
  note:
    title: Note
    description: A note.
  hidden:
    title: Hidden
    description: Written by the toolkit, never by a client.
    required: true
    annotations: {internal: true}
"""


@pytest.fixture(scope="module")
def identified_shapes(tmp_path_factory: pytest.TempPathFactory) -> Graph:
    path = tmp_path_factory.mktemp("identified") / "identified.yaml"
    path.write_text(IDENTIFIED, encoding="utf-8")
    return Graph().parse(data=render(path)[0].text, format="turtle")


def test_the_shape_of_an_identified_class_requires_an_iri_node(identified_shapes: Graph) -> None:
    shape = URIRef("https://example.org/ns/s#Named")
    assert (shape, SH.nodeKind, SH.IRI) in identified_shapes, "a node with an identifier is an IRI"


def test_the_shape_of_a_class_without_an_identifier_has_no_node_kind(
    identified_shapes: Graph,
) -> None:
    shape = URIRef("https://example.org/ns/s#Anonymous")
    assert (shape, SH.nodeKind, None) not in identified_shapes, "a blank node is allowed"


def test_an_internal_slot_is_optional_in_the_shape_though_the_class_requires_it(
    identified_shapes: Graph,
) -> None:
    path = URIRef("https://example.org/ns/s#hidden")
    shape = URIRef("https://example.org/ns/s#Named")
    (prop,) = [
        p
        for p in identified_shapes.objects(shape, SH.property)
        if (p, SH.path, path) in identified_shapes
    ]
    assert (prop, SH.minCount, None) not in identified_shapes, (
        "the toolkit writes it, not the client"
    )
    assert (prop, SH.maxCount, None) in identified_shapes, "the rest of the property stays"
