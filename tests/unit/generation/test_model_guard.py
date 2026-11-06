"""Spec rp-generation: a hand-written domain class is caught, and this repo has none (PD-28)."""

import shutil
from pathlib import Path

import pytest

from rdf_persistence.testkit.guards import SCANNED_LAYERS, assert_models_generated

REPO = Path(__file__).resolve().parents[3]


def test_hand_written_domain_class_fails_the_guard_and_names_it(tmp_path):
    shutil.copytree(
        REPO / "rdf_persistence",
        tmp_path / "rdf_persistence",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    planted = tmp_path / "rdf_persistence" / "domain" / "handwritten.py"
    planted.write_text(
        "from pydantic import BaseModel\n\n\nclass Handwritten(BaseModel):\n    x: int\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError) as err:
        assert_models_generated(tmp_path / "rdf_persistence", roots=[])
    assert "Handwritten" in str(err.value), "the class is named"
    assert "domain/handwritten.py:4" in str(err.value), "the file and line are named"


@pytest.mark.parametrize("layer", ["adapters", "generation", "testkit"])
def test_a_hand_written_record_in_a_widened_layer_is_caught_only_when_the_layer_is_scanned(
    tmp_path, layer
):
    shutil.copytree(
        REPO / "rdf_persistence",
        tmp_path / "rdf_persistence",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "rdf_persistence" / layer / "record.py").write_text(
        "from dataclasses import dataclass\n\n\n@dataclass\nclass Record:\n    x: int\n",
        encoding="utf-8",
    )
    package = tmp_path / "rdf_persistence"
    assert_models_generated(package, roots=[], allow=HAND_WRITTEN)  # the default layers ignore it
    with pytest.raises(AssertionError, match=f"{layer}/record.py:5"):
        assert_models_generated(package, roots=[], layers=(layer,), allow=HAND_WRITTEN)


# Every plain data record of adapters, generation and testkit is generated (PD-24); what stays hand-written
# holds a foreign runtime object that LinkML cannot express.
# A type that subclasses a LinkML generator or template class is not flagged by the guard, so it
# needs no entry here.
HAND_WRITTEN = (
    # holds a SchemaView, the loaded schema a step reads
    "rdf_persistence/generation/pipeline.py:Run",
    # holds a callable, the function a step runs
    "rdf_persistence/generation/pipeline.py:Step",
    # a dataclass subclass of gen-pydantic's PydanticGenerator, configured by its own fields
    "rdf_persistence/generation/extensions/pydantic_split.py:SplitPydanticGenerator",
    # a dataclass subclass of gen-shacl's ShaclGenerator
    "rdf_persistence/generation/extensions/shacl.py:RpShaclGenerator",
    # holds a SchemaView, the generated classes and an rdflib Graph of the shapes
    "rdf_persistence/testkit/conformance.py:Conformance",
)


def test_this_repo_has_no_hand_written_model_or_generated_artefact_outside_generated():
    assert_models_generated(
        "rdf_persistence",
        roots=[REPO / "rdf_persistence", REPO / "tests"],
        exempt=[REPO / "tests" / "fixtures"],
        layers=(*SCANNED_LAYERS, "adapters", "generation", "testkit"),
        allow=HAND_WRITTEN,
    )


def test_every_hand_written_type_in_the_allow_list_still_exists_and_is_flagged_without_it():
    """An entry that names nothing is dead weight; drop it when the type is generated or gone."""
    with pytest.raises(AssertionError) as err:
        assert_models_generated(
            "rdf_persistence", roots=[], layers=(*SCANNED_LAYERS, "generation", "testkit")
        )
    for entry in HAND_WRITTEN:
        path, name = entry.split(":")
        assert f"{path}:" in str(err.value) and f"class {name} " in str(err.value), (
            f"{entry} is allowed but the guard does not flag it"
        )


def test_the_default_layers_leave_generation_and_testkit_alone_so_consumers_are_unaffected():
    assert SCANNED_LAYERS == ("domain", "services", "entrypoints"), "the consumer default changed"
    assert_models_generated("rdf_persistence", roots=[])
