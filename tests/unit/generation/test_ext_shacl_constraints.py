"""Golden test and behaviour of the shape constraints for declared rules (PD-24, PD-25)."""

from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import RDF, SH

from rdf_persistence.generation.extensions.shacl import render_shapes
from rdf_persistence.generation.extensions.shacl_constraints import (
    UniqueKeyOn,
    constraints_graph,
    unique_key_query,
)
from rdf_persistence.services.schema import load_schema

from .conftest import ROOT_SCHEMA, TOY
from .golden import assert_matches_golden

CONTACT = """
id: https://example.org/ns/contact
name: contact
title: Contact
description: A schema with a class-level any_of.
prefixes: {c: "https://example.org/ns/c#", linkml: "https://w3id.org/linkml/"}
default_prefix: c
default_range: string
imports: [linkml:types]
classes:
  Contact:
    title: Contact
    description: A contact reachable by e-mail or by phone.
    slots: [email, phone]
    any_of:
      - slot_conditions: {email: {required: true}}
      - slot_conditions: {phone: {required: true}}
slots:
  email: {title: E-mail, description: The e-mail address., slot_uri: "c:email"}
  phone: {title: Phone, description: The phone number., slot_uri: "c:phone"}
"""
CONTACT_DATA = "@prefix c: <https://example.org/ns/c#> . <https://example.org/x> a c:Contact ; {} ."


def test_the_toy_constraints_match_the_golden_graph(tmp_path: Path) -> None:
    graph = to_canonical_graph(constraints_graph(load_schema(TOY / ROOT_SCHEMA)))
    graph.serialize(tmp_path / "constraints.ttl", format="turtle")
    assert_matches_golden("shacl_constraints", tmp_path)


def test_exactly_one_of_becomes_xone_on_the_class_that_declares_it() -> None:
    view = load_schema(TOY / ROOT_SCHEMA)
    graph = constraints_graph(view)
    grant = [s for s in graph.subjects(SH.xone) if str(s).endswith("#Grant")]
    assert len(grant) == 1, "Grant declares exactly_one_of, so its shape must carry one sh:xone"


def test_a_subclass_inherits_the_rule_of_its_parent(tmp_path: Path) -> None:
    colleague = "  Colleague:\n    title: Colleague\n    description: A contact at work.\n    is_a: Contact\n"
    schema = CONTACT.replace("slots:\n  email", colleague + "slots:\n  email")
    path = tmp_path / "contact.yaml"
    path.write_text(schema, encoding="utf-8")
    graph = constraints_graph(load_schema(path))
    carriers = {str(s).rsplit("#", 1)[1] for s in graph.subjects(SH["or"])}
    assert carriers == {"Contact", "Colleague"}, "the subclass must carry the any_of of its parent"


def test_a_subclass_of_the_owner_gets_the_unique_key_too() -> None:
    graph = constraints_graph(load_schema(TOY / ROOT_SCHEMA))
    owners = {str(s).rsplit("#", 1)[1] for s in graph.subjects(SH.sparql)}
    assert owners == {"TenantAccess", "LibraryAccess"}, "only the owners of grants carry the key"


def test_the_unique_key_query_treats_absent_values_as_equal() -> None:
    on = UniqueKeyOn("grants", URIRef("http://e/grant"), "k", None, (URIRef("http://e/a"),))
    query = unique_key_query(on)
    assert "(!bound(?first_0) && !bound(?second_0))" in query, "two absent values must be equal"


def test_the_unique_key_query_is_the_same_on_every_call() -> None:
    graph = constraints_graph(load_schema(TOY / ROOT_SCHEMA))
    again = constraints_graph(load_schema(TOY / ROOT_SCHEMA))
    assert sorted(map(str, graph.objects(None, SH.select))) == sorted(
        map(str, again.objects(None, SH.select))
    ), "the same schema must give the same queries"


def contact_shapes(tmp_path: Path, schema: str = CONTACT) -> Graph:
    path = tmp_path / "contact.yaml"
    path.write_text(schema, encoding="utf-8")
    return Graph().parse(data=render_shapes(path).text, format="turtle")


@pytest.mark.parametrize(
    ("triples", "conforms"),
    [
        ('c:email "a@b.c"', True),
        ('c:phone "123"', True),
        ('c:email "a@b.c" ; c:phone "123"', True),
        ("", False),
    ],
    ids=["email only", "phone only", "both", "neither"],
)
def test_any_of_becomes_or_and_one_alternative_is_enough(
    tmp_path: Path, triples: str, conforms: bool
) -> None:
    shapes = contact_shapes(tmp_path)
    assert (None, SH["or"], None) in shapes, "any_of must become sh:or"
    data = Graph().parse(data=CONTACT_DATA.format(triples or "a c:Contact"), format="turtle")
    assert validate(data, shacl_graph=shapes, inference="none")[0] is conforms, (
        f"a contact with {triples or 'neither'}"
    )


def test_a_condition_other_than_presence_is_refused_not_dropped(tmp_path: Path) -> None:
    schema = CONTACT.replace("{email: {required: true}}", "{email: {equals_string: x}}")
    with pytest.raises(ValueError, match="email"):
        contact_shapes(tmp_path, schema)


def test_the_shapes_name_the_missing_alternative_in_the_report(tmp_path: Path) -> None:
    shapes = contact_shapes(tmp_path)
    data = Graph().parse(data=CONTACT_DATA.format("a c:Contact"), format="turtle")
    _, report, _ = validate(data, shacl_graph=shapes, inference="none")
    assert (None, SH.sourceConstraintComponent, SH.OrConstraintComponent) in report, (
        "the report must name sh:or"
    )
    assert (None, RDF.type, SH.ValidationResult) in report, "the report must hold a result"
