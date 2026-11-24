"""The runtime reads a slot over an abstract aggregate root as a reference, as the kit loads the schema (DEC-6, #303).

The kit opens the schema with ``load_schema``, which does not apply the generation defaults, so the
mapper, ``SchemaView.is_inlined`` and the keyed-slot reader must reach the verdict without them.
"""

from pathlib import Path

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, URIRef

from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.schema.services.schema import load_schema, metamodel_importmap
from rdf_persistence.schema.services.schema_structure import _holds_objects
from tests.fixtures.library.domain.generated.books import Loan
from tests.toy import TENANT, TOY_SCHEMA, toy_mapper

LIB = "https://example.org/ns/library#"
LOAN = f"{TENANT}/loans/00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize("kind", ["magazines", "pamphlets"])
def test_a_loan_of_an_item_maps_to_the_iri_and_reads_back_as_it(kind: str) -> None:
    mapper = toy_mapper()
    item = f"{TENANT}/{kind}/00000000-0000-0000-0000-000000000002"
    graph = mapper.to_graph(Loan(id=LOAN, label="A loan", lends=item))
    assert (URIRef(LOAN), URIRef(f"{LIB}lends"), URIRef(item)) in graph, "the IRI is the object"
    assert (URIRef(item), RDF.type, None) not in graph, "the item is not described here"
    back = mapper.from_graph(Loan, LOAN, graph, graph_iri(LOAN))
    assert back.lends == item, "the reference reads back as the IRI string"


def test_loading_the_toy_leaves_the_source_module_unchanged() -> None:
    raw = SchemaView(str(TOY_SCHEMA), importmap=metamodel_importmap())
    assert raw.get_identifier_slot("LendingItem") is None, "the source has no identifier there"
    assert load_schema(TOY_SCHEMA).get_identifier_slot("LendingItem") is not None, (
        "the loaded view gives the abstract root the identifier of its kinds"
    )
    assert raw.get_identifier_slot("LendingItem") is None, "loading did not touch the source"


SCRATCH = """
id: https://example.org/ns/scratch
name: scratch
title: Scratch
description: Abstract aggregate roots in every shape the runtime meets.
prefixes: {s: "https://example.org/ns/s#", linkml: "https://w3id.org/linkml/"}
default_prefix: s
default_range: string
imports: [linkml:types, rdf_persistence/model/rp_core, rdf_persistence/model/rp_annotations]
classes:
  Item:
    title: Item
    description: An abstract root.
    abstract: true
    mixins: [AggregateRoot]
  Mag:
    title: Mag
    description: A kind of item.
    is_a: Item
    mixins: [Described]
  Orphan:
    title: Orphan
    description: An abstract root with no kind.
    abstract: true
    mixins: [AggregateRoot]
  Marker:
    title: Marker
    description: An abstract mixin that is not a class to point at.
    abstract: true
    mixin: true
    mixins: [AggregateRoot]
  Holder:
    title: Holder
    description: Points at items.
    mixins: [AggregateRoot, Described]
    slots: [one_item, many_items, many_parts, one_orphan]
  Part:
    title: Part
    description: An owned part.
    mixins: [Described]
slots:
  one_item: {title: One, description: One item., range: Item}
  many_items: {title: Many, description: Many items., range: Item, multivalued: true}
  many_parts: {title: Parts, description: Owned parts., range: Part, multivalued: true, inlined_as_list: true}
  one_orphan: {title: Orphan, description: An orphan., range: Orphan}
"""

CLASHING = SCRATCH.replace(
    "  Holder:",
    """  Coded:
    title: Coded
    description: A kind of item identified by a code, not by the identifier.
    is_a: Item
    slots: [code]
  Holder:""",
).replace(
    "slots:\n  one_item",
    "slots:\n  code: {title: Code, description: The code., identifier: true}\n  one_item",
)


def scratch(tmp_path: Path, text: str = SCRATCH) -> Path:
    path = tmp_path / "scratch.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("slot", "holds_objects"),
    [
        pytest.param("one_item", False, id="abstract-root-single"),
        pytest.param("many_items", False, id="abstract-root-multivalued"),
        pytest.param("many_parts", True, id="owned-part-multivalued"),
    ],
)
def test_the_runtime_view_reads_a_slot_over_an_abstract_root_as_a_reference(
    tmp_path: Path, slot: str, holds_objects: bool
) -> None:
    view = load_schema(scratch(tmp_path))
    induced = view.induced_slot(slot, "Holder")
    assert _holds_objects(view, induced) is holds_objects, (
        f"{slot}: holds objects, not {holds_objects}"
    )
    assert bool(view.is_inlined(induced)) is holds_objects, (
        f"{slot}: is_inlined, not {holds_objects}"
    )


@pytest.mark.parametrize(
    ("class_name", "given"),
    [
        pytest.param("Item", True, id="abstract-root-with-kinds"),
        pytest.param("Orphan", False, id="abstract-root-with-no-kind"),
        pytest.param("Marker", False, id="abstract-mixin"),
        pytest.param("Mag", True, id="concrete-kind"),
    ],
)
def test_only_an_abstract_root_with_kinds_is_given_the_identifier_of_them(
    tmp_path: Path, class_name: str, given: bool
) -> None:
    view = load_schema(scratch(tmp_path))
    assert (view.get_identifier_slot(class_name) is not None) is given, (
        f"{class_name} has an identifier: {not given}"
    )


def test_kinds_with_different_identifier_slots_are_refused_naming_the_class_and_the_slots(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match=r"Item.*\['code', 'id'\]"):
        load_schema(scratch(tmp_path, CLASHING))
