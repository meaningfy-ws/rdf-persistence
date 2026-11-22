"""A slot name resolves to the application's slot whatever the import order (#278)."""

from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.vocabulary import VERSION, metamodel

SHELVES = """
id: https://example.org/shelves
name: shelves
title: Shelves
description: A module that defines its own slot named version.
prefixes: {linkml: "https://w3id.org/linkml/", lib: "https://example.org/lib#", dcat: "http://www.w3.org/ns/dcat#"}
default_prefix: lib
default_range: string
imports: [linkml:types, rdf_persistence/model/rp_annotations, rdf_persistence/model/rp_core]
slots:
  version: {title: Version, description: The edition., slot_uri: dcat:version, range: string}
classes:
  Shelf:
    title: Shelf
    description: A shelf.
    class_uri: lib:Shelf
    mixins: [AggregateRoot, Described]
    slots: [version]
"""
ROOT = """
id: https://example.org/root
name: root
title: Root
description: The root.
prefixes: {linkml: "https://w3id.org/linkml/", lib: "https://example.org/lib#"}
default_prefix: lib
default_range: string
imports: [linkml:types, IMPORTS]
"""
DCAT_VERSION = "http://www.w3.org/ns/dcat#version"
TOOLKIT = "rdf_persistence/model/rp_annotations, rdf_persistence/model/rp_core"


@pytest.mark.parametrize(
    "imports", [f"shelves, {TOOLKIT}", f"{TOOLKIT}, shelves"], ids=["module-first", "toolkit-first"]
)
def test_the_application_slot_wins_in_the_view_and_in_the_merged_schema(
    tmp_path: Path, imports: str
) -> None:
    (tmp_path / "shelves.yaml").write_text(SHELVES)
    (tmp_path / "root.yaml").write_text(ROOT.replace("IMPORTS", imports))
    view = load_schema(tmp_path / "root.yaml")
    slot = {s.name: s for s in view.class_induced_slots("Shelf")}["version"]
    assert view.get_uri(slot, expand=True) == DCAT_VERSION, "the mapper's and the shapes' view"
    view.merge_imports()
    assert view.expand_curie(view.schema.slots["version"].slot_uri) == DCAT_VERSION, "the context's"


def test_a_toolkit_slot_a_toolkit_class_carries_stays_in_the_view(tmp_path: Path) -> None:
    """``graph`` is carried by the registry entry: the clash stays for the hard check to refuse."""
    clash = "  graph: {title: Graph, description: Its own., slot_uri: lib:graph}\n"
    (tmp_path / "shelves.yaml").write_text(SHELVES.replace("slots:\n", f"slots:\n{clash}", 1))
    (tmp_path / "root.yaml").write_text(ROOT.replace("IMPORTS", f"shelves, {TOOLKIT}"))
    view = load_schema(tmp_path / "root.yaml")
    core = view.schema_map["rdf_persistence/model/rp_core"]
    assert "graph" in core.slots, "a carried toolkit slot never gives way"
    assert "version" not in core.slots, "the uncarried one did"


def test_the_toolkit_keeps_its_own_version() -> None:
    assert str(VERSION).endswith("rdf-persistence#version"), "the session's predicate"
    assert metamodel().get_slot("version").slot_uri == "rp:version", "the metamodel is untouched"
