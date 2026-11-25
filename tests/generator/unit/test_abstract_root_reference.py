"""A slot over an aggregate root is a reference in every artefact, abstract root or concrete (DEC-6, #303)."""

import re
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from rdflib import Namespace, URIRef
from rdflib.namespace import SH

from rdf_persistence_generation.testkit.conformance import Conformance
from rdf_persistence_generation.testkit.roundtrip import round_trip
from rdf_persistence_generation.testkit.strategies import IRI_BASE, aggregate
from tests.toy import BIBO as BIBO_IRI

ROOT = Path(__file__).parents[3]
TOY = ROOT / "tests" / "fixtures" / "library"
TOY_SCHEMA = TOY / "library.yaml"
# committed output: `make check-freshness` covers it, the manifest of the toy's domain folder lists it
TOY_TYPESCRIPT = TOY / "web" / "src" / "domain" / "generated" / "books.ts"
LIB = Namespace("https://example.org/ns/library#")
BIBO = Namespace(BIBO_IRI)

# (class, slot, the class an embedded value is, or None for a reference)
SLOTS = [
    pytest.param("Loan", "lends", None, id="abstract-root-is-a-reference"),
    pytest.param("Book", "sequel_of", None, id="concrete-root-is-a-reference"),
    pytest.param("Book", "chapters", "Chapter", id="owned-part-is-embedded"),
]


@cache
def opened() -> Conformance:
    """The toy and its generated artefacts, opened once."""
    return Conformance.of(TOY_SCHEMA)


def interface_of(name: str) -> str:
    """The body of the TypeScript interface ``name`` in the committed toy file."""
    source = TOY_TYPESCRIPT.read_text(encoding="utf-8")
    match = re.search(rf"export interface {name}\b[^{{]*\{{(.*?)\n\}}", source, re.DOTALL)
    assert match, f"no interface {name} in {TOY_TYPESCRIPT.name}"
    return match.group(1)


def chapters_of(models: Mapping[str, type]) -> object:
    """The annotation of the embedded chapters: a list of the generated ``Chapter``, optional."""
    chapter = models["Chapter"]
    return list[chapter] | None


@pytest.mark.parametrize(
    ("class_name", "slot", "expected"),
    [
        pytest.param("Loan", "lends", lambda models: str, id="abstract-root-is-a-string"),
        pytest.param(
            "Book", "sequel_of", lambda models: str | None, id="concrete-root-is-a-string"
        ),
        pytest.param("Book", "chapters", chapters_of, id="owned-part-is-embedded"),
    ],
)
def test_the_python_field_of_a_slot_over_a_root_is_a_string(
    class_name: str, slot: str, expected: Callable[[Mapping[str, type]], object]
) -> None:
    models = opened().models
    annotation = models[class_name].model_fields[slot].annotation
    assert annotation == expected(models), f"{class_name}.{slot} is {annotation}"


@pytest.mark.parametrize(("class_name", "slot", "embedded"), SLOTS)
def test_the_typescript_field_of_a_slot_over_a_root_is_a_string(
    class_name: str, slot: str, embedded: str | None
) -> None:
    field = re.search(rf"\b{slot}\??: ([^;]+);", interface_of(class_name))
    assert field, f"{class_name} has no field {slot}"
    expected = "string" if embedded is None else f"{embedded}[]"
    assert field.group(1) == expected, f"{class_name}.{slot} is {field.group(1)}, not {expected}"


@pytest.mark.parametrize(
    ("class_iri", "slot_iri"),
    [
        pytest.param(LIB.Loan, LIB.lends, id="abstract-root"),
        pytest.param(BIBO.Book, LIB.sequelOf, id="concrete-root"),
    ],
)
def test_the_shape_of_a_slot_over_a_root_asks_for_an_iri(
    class_iri: URIRef, slot_iri: URIRef
) -> None:
    """An owned part is a node of the aggregate's graph with an IRI too, so only references are tabled."""
    shapes = opened().shapes
    properties = [
        prop
        for shape in shapes.subjects(SH.targetClass, class_iri)
        for prop in shapes.objects(shape, SH.property)
        if (prop, SH.path, slot_iri) in shapes
    ]
    assert len(properties) == 1, f"{slot_iri} has {len(properties)} property shapes"
    assert (properties[0], SH.nodeKind, SH.IRI) in shapes, f"{slot_iri} does not ask for an IRI"


def test_the_shape_of_an_abstract_root_has_no_property_for_the_identifier() -> None:
    """The identifier is never a property of a shape (#277); the abstract root only names it."""
    shapes = opened().shapes
    properties = [
        prop
        for shape in shapes.subjects(SH.targetClass, LIB.LendingItem)
        for prop in shapes.objects(shape, SH.property)
    ]
    assert properties == [], f"LendingItem has property shapes {properties}"


@pytest.mark.parametrize("kind", ["Magazine", "Pamphlet"])
def test_a_loan_accepts_the_iri_of_any_kind_of_item(kind: str) -> None:
    toy = opened()
    loan = toy.models["Loan"].model_validate(
        {"id": f"{IRI_BASE}loan", "label": "A loan", "lends": f"{IRI_BASE}{kind.lower()}-1"}
    )
    assert loan.lends == f"{IRI_BASE}{kind.lower()}-1", f"the IRI of a {kind} is kept as a string"


@given(data=st.data())
def test_a_loan_survives_json_rdf_and_a_frame(data: st.DataObject) -> None:
    toy = opened()
    round_trip(toy, data.draw(aggregate(toy, "Loan")), "Loan")
