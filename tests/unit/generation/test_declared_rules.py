"""The generated classes and the generated shapes read a schema's declared rules alike (PD-24, PD-22)."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import SH

from rdf_persistence.generation.exceptions import SchemaGenerationError
from rdf_persistence.generation.extensions.pydantic_split import render as render_modules
from rdf_persistence.generation.extensions.shacl import render as render_shapes
from rdf_persistence.generation.generated.rp_generation import ConstraintKind
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from rdf_persistence.testkit.conformance import Conformance

SHAPE_BASE = "https://example.org/ns/r#"

SCHEMA = """
id: https://example.org/ns/rules
name: rules
title: Rules
description: Classes that declare keyed slots and presence rules.
prefixes: {r: "https://example.org/ns/r#", linkml: "https://w3id.org/linkml/"}
default_prefix: r
default_range: string
imports: [linkml:types]
classes:
  Entry:
    title: Entry
    description: An entry, one per name and tag.
    slots: [name, tag]
    unique_keys:
      entry_key: {unique_key_slots: [name, tag]}
  Dated:
    title: Dated
    description: An entry that is one per name.
    is_a: Entry
    unique_keys:
      entry_key: {unique_key_slots: [name]}
  Account:
    title: Account
    description: An account, referred to by identifier.
    slots: [acct, name]
    unique_keys:
      account_key: {unique_key_slots: [name]}
  Ledger:
    title: Ledger
    description: Entries and accounts.
    slots: [entries, dated, accounts]
  Contact:
    title: Contact
    description: A contact reachable by mail or phone.
    slots: [mail, phone]
    any_of:
      - slot_conditions: {mail: {name: mail, required: true, value_presence: ABSENT}}
      - slot_conditions: {phone: {name: phone, required: true}}
slots:
  name: {title: Name, description: The name., range: string}
  tag: {title: Tag, description: The tag., range: string}
  mail: {title: Mail, description: The mail address., range: string}
  phone: {title: Phone, description: The phone number., range: string}
  acct: {title: Account id, description: The identifier., range: string, identifier: true}
  entries: {title: Entries, description: The entries., range: Entry, multivalued: true, inlined_as_list: true}
  dated: {title: Dated, description: The dated entries., range: Dated, multivalued: true, inlined_as_list: true}
  accounts: {title: Accounts, description: The accounts by identifier., range: Account, multivalued: true}
"""
WITHOUT_BAD_RULE = SCHEMA.replace("required: true, value_presence: ABSENT", "required: true")


def write(tmp_path: Path, schema: str) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(schema, encoding="utf-8")
    return path


def class_source(path: Path) -> str:
    return "".join(module.text for module in render_modules(path))


def shapes(path: Path) -> Graph:
    return Graph().parse(data=render_shapes(path)[0].text, format="turtle")


def constraints_on(graph: Graph, cls: str) -> list[str]:
    return [
        str(q)
        for c in graph.objects(URIRef(SHAPE_BASE + cls), SH.sparql)
        for q in graph.objects(c, SH.select)
    ]


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return write(tmp_path, WITHOUT_BAD_RULE)


def test_a_slot_that_refers_by_identifier_gets_neither_a_validator_nor_a_constraint(
    path: Path,
) -> None:
    source = class_source(path)
    queries = constraints_on(shapes(path), "Ledger")
    assert "unique_keys_accounts" not in source, "the classes must not compare references"
    assert not any("accounts" in q for q in queries), "the shapes must not compare references"


def test_a_subclass_redeclaring_a_key_name_gets_exactly_one_validator_and_one_constraint(
    path: Path,
) -> None:
    source = class_source(path)
    queries = constraints_on(shapes(path), "Ledger")
    assert source.count("def unique_keys_dated_entry_key") == 1, "one validator for dated"
    assert len([q for q in queries if "r#dated" in q]) == 1, "one constraint for dated"
    assert len([q for q in queries if "r#entries" in q]) == 1, "one constraint for entries"


@pytest.mark.parametrize("generate", [class_source, shapes], ids=["classes", "shapes"])
def test_a_condition_both_required_and_absent_is_refused_alike(
    tmp_path: Path, generate: Callable[[Path], object]
) -> None:
    with pytest.raises(SchemaGenerationError, match=r"Contact.*any_of.*mail.*exactly one of"):
        generate(write(tmp_path, SCHEMA))


# Dated keeps no key of its own, only its parent Entry has one; Cellar narrows entries to Dated.
CELLAR = """  Cellar:
    title: Cellar
    description: A ledger whose entries are all dated.
    is_a: Ledger
    slot_usage:
      entries: {range: Dated}
slots:
  name:"""
NARROWED = WITHOUT_BAD_RULE.replace(
    "    unique_keys:\n      entry_key: {unique_key_slots: [name]}\n", ""
).replace("slots:\n  name:", CELLAR, 1)


def test_a_narrowed_slot_counts_the_unique_keys_of_the_ancestors_of_its_new_range(
    tmp_path: Path,
) -> None:
    conformance = Conformance(
        view=load_schema(write(tmp_path, NARROWED)),
        models={},
        shapes=Graph(),
        documents=create_autospec(
            Documents, instance=True
        ),  # the kinds are read from the view alone
    )
    assert ConstraintKind.UNIQUE_KEYS in conformance.class_kinds("Cellar"), (
        "the keys of the ancestors of the narrowed range govern the slot"
    )
