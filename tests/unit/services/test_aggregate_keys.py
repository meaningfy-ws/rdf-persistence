"""The keys across aggregates a schema declares, read from its view (cross-aggregate-unique-keys PD-3)."""

from pathlib import Path

from rdf_persistence.domain.generated.rp_core import AggregateKey
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import aggregate_keys
from tests.toy import TOY_SCHEMA

BIBO = "http://purl.org/ontology/bibo/"
R = "https://example.org/ns/r#"

HEAD = """
id: https://example.org/ns/keys
name: keys
title: Keys
description: Roots that declare keys across aggregates.
prefixes: {r: "https://example.org/ns/r#", linkml: "https://w3id.org/linkml/"}
default_prefix: r
default_range: string
imports: [linkml:types, rdf_persistence/model/rp_core]
"""

SLOTS = """
slots:
  title: {title: Title, description: The title., range: string}
  issn: {title: ISSN, description: The ISSN., range: string}
"""

SCOPED = "annotations: {rp_unique_scope: tenant}"

PUBLICATIONS = (
    HEAD
    + f"""
classes:
  Publication:
    title: Publication
    description: Anything published; one title per type.
    abstract: true
    mixins: [AggregateRoot]
    slots: [title, issn]
    unique_keys:
      title_key: {{unique_key_slots: [title], {SCOPED}}}
  Book2:
    title: Book
    description: A book.
    is_a: Publication
  Magazine:
    title: Magazine
    description: A magazine, one per ISSN.
    is_a: Publication
    unique_keys:
      title_key: {{unique_key_slots: [issn], {SCOPED}}}
"""
    + SLOTS
)

SYSTEM_AND_UNSCOPED = (
    HEAD
    + f"""
classes:
  Ledger:
    title: Ledger
    description: A root of the system database.
    mixins: [AggregateRoot]
    slots: [title]
    unique_keys:
      title_key: {{unique_key_slots: [title], {SCOPED}}}
    annotations: {{database: system}}
  Plain:
    title: Plain
    description: A root with an in-aggregate key only.
    mixins: [AggregateRoot]
    slots: [title]
    unique_keys:
      title_key: {{unique_key_slots: [title]}}
"""
    + SLOTS
)


def keys_of(tmp_path: Path, schema: str) -> list[AggregateKey]:
    path = tmp_path / "keys.yaml"
    path.write_text(schema, encoding="utf-8")
    return aggregate_keys(load_schema(path))


def test_the_toy_library_has_one_key_across_aggregates() -> None:
    assert aggregate_keys(load_schema(TOY_SCHEMA)) == [
        AggregateKey(key_name="isbn_key", root_class=f"{BIBO}Book", key_predicates=[f"{BIBO}isbn"])
    ], "TC-01: Book's isbn_key, and no other root has a scoped key"


def test_a_root_gets_the_scoped_keys_it_inherits_and_the_nearest_declaration_wins(
    tmp_path: Path,
) -> None:
    assert keys_of(tmp_path, PUBLICATIONS) == [
        AggregateKey(key_name="title_key", root_class=f"{R}Book2", key_predicates=[f"{R}title"]),
        AggregateKey(key_name="title_key", root_class=f"{R}Magazine", key_predicates=[f"{R}issn"]),
    ], (
        "TC-02: the abstract Publication is no root; Magazine's own declaration replaces the inherited"
    )


def test_a_system_database_root_and_an_unscoped_key_give_no_entry(tmp_path: Path) -> None:
    assert keys_of(tmp_path, SYSTEM_AND_UNSCOPED) == [], (
        "a key across aggregates is for the tenant databases, and the annotation tells the kinds apart"
    )
