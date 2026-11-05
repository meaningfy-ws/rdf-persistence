"""Golden test and behaviour of the gen-shacl extension (PD-7, PD-24, PD-25)."""

from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, RDF, SH

from rdf_persistence.generation.extensions.shacl import render_shapes

from .golden import assert_matches_golden

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


def test_the_toy_shapes_match_the_golden_file(generated_toy: Path, tmp_path: Path) -> None:
    (tmp_path / "shapes.ttl").write_bytes((generated_toy / "shapes.ttl").read_bytes())
    assert_matches_golden("shacl", tmp_path)


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
    graph = Graph().parse(data=render_shapes(path).text, format="turtle")
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
