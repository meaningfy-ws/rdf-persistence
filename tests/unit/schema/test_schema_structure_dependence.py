"""The links of dependence a schema declares, read from its view (dependent-aggregates PD-2, D-6)."""

from pathlib import Path

from rdf_persistence.core.domain.generated.rp_core import DependenceLink
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import dependence_links

R = "https://example.org/ns/r#"

HEAD = """
id: https://example.org/ns/dependence
name: dependence
title: Dependence
description: Roots that depend on other roots.
prefixes: {r: "https://example.org/ns/r#", linkml: "https://w3id.org/linkml/"}
default_prefix: r
default_range: string
imports: [linkml:types, rdf_persistence/model/rp_core]
"""

WHOLES = """
classes:
  Shelf:
    title: Shelf
    description: A whole.
    mixins: [AggregateRoot]
    annotations: {rp_path: shelves}
  BigShelf:
    title: Big shelf
    description: A kind of whole.
    is_a: Shelf
    annotations: {rp_path: big-shelves}
"""

SLOTS = """
slots:
  shelf: {title: Shelf, description: The whole., range: Shelf, required: true}
  subject: {title: Subject, description: The whole., range: Shelf, required: true}
"""

CONCRETE_PART = (
    HEAD
    + WHOLES
    + """
  Audit:
    title: Audit
    description: A part, annotated itself.
    mixins: [AggregateRoot]
    slots: [shelf]
    annotations: {rp_path: audits, rp_dependent_on: shelf}
  Plain:
    title: Plain
    description: A root that depends on nothing.
    mixins: [AggregateRoot]
    annotations: {rp_path: plains}
"""
    + SLOTS
)

ABSTRACT_BASE = (
    HEAD
    + WHOLES
    + """
  Note:
    title: Note
    description: An abstract base of parts.
    abstract: true
    mixins: [AggregateRoot]
    slots: [subject]
    annotations: {rp_dependent_on: subject}
  Memo:
    title: Memo
    description: A part.
    is_a: Note
    annotations: {rp_path: memos}
  Remark:
    title: Remark
    description: Another part.
    is_a: Note
    annotations: {rp_path: remarks}
"""
    + SLOTS
)


def links_of(tmp_path: Path, schema: str) -> list[DependenceLink]:
    path = tmp_path / "dependence.yaml"
    path.write_text(schema, encoding="utf-8")
    return dependence_links(load_schema(path))


def test_dependence_links_read_the_annotation_and_subclasses(tmp_path: Path) -> None:
    assert links_of(tmp_path, CONCRETE_PART) == [
        DependenceLink(
            part_classes=[f"{R}Audit"],
            pointer=f"{R}shelf",
            whole_classes=[f"{R}BigShelf", f"{R}Shelf"],
        )
    ], (
        "PD-2: one link for Audit; the whole is its range and the concrete subclasses of it; Plain has none"
    )


def test_an_abstract_annotated_base_gives_one_link_with_its_concrete_subclasses(
    tmp_path: Path,
) -> None:
    assert links_of(tmp_path, ABSTRACT_BASE) == [
        DependenceLink(
            part_classes=[f"{R}Memo", f"{R}Remark"],
            pointer=f"{R}subject",
            whole_classes=[f"{R}BigShelf", f"{R}Shelf"],
        )
    ], "PD-2: the abstract Note is no part itself; one link lists Memo and Remark, sorted"
