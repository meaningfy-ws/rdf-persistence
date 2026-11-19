"""Spec rp-generation: a hand-written domain class is caught, and this repo has none (PD-28)."""

import shutil
from pathlib import Path

import pytest

from rdf_persistence.testkit.guards import SCANNED_LAYERS, assert_models_generated
from tests.unit.test_theme_layout import TURNED_ON

REPO = Path(__file__).resolve().parents[3]
GENERATOR = "rdf_persistence_generation"


def test_hand_written_domain_class_fails_the_guard_and_names_it(tmp_path):
    shutil.copytree(
        REPO / "rdf_persistence",
        tmp_path / "rdf_persistence",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    planted = tmp_path / "rdf_persistence" / "core" / "domain" / "handwritten.py"
    planted.write_text(
        "from pydantic import BaseModel\n\n\nclass Handwritten(BaseModel):\n    x: int\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError) as err:
        assert_models_generated(tmp_path / "rdf_persistence", roots=[], layers=("core",))
    assert "Handwritten" in str(err.value), "the class is named"
    assert "core/domain/handwritten.py:4" in str(err.value), "the file and line are named"


@pytest.mark.parametrize(
    ("name", "layer"),
    [
        ("rdf_persistence", "persistence"),  # a theme: every layer folder of it
        ("rdf_persistence", "testkit"),
        (GENERATOR, ""),  # the generator is a package of its own: its whole tree is the layer
    ],
    ids=["theme", "testkit", "generator"],
)
def test_a_hand_written_record_in_a_widened_layer_is_caught_only_when_the_layer_is_scanned(
    tmp_path, name, layer
):
    shutil.copytree(
        REPO / name,
        tmp_path / name,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / name / layer / "record.py").write_text(
        "from dataclasses import dataclass\n\n\n@dataclass\nclass Record:\n    x: int\n",
        encoding="utf-8",
    )
    package = tmp_path / name
    where = f"{name}/{layer}/" if layer else f"{name}/"
    assert_models_generated(package, roots=[], allow=HAND_WRITTEN)  # the default layers ignore it
    with pytest.raises(AssertionError, match=f"{where}record.py:5"):
        assert_models_generated(package, roots=[], layers=(layer,), allow=HAND_WRITTEN)


# Every plain data record of adapters, generation and testkit is generated (PD-24); what stays hand-written
# holds a foreign runtime object that LinkML cannot express.
# A type that subclasses a LinkML generator or template class is not flagged by the guard, so it
# needs no entry here.
HAND_WRITTEN = (
    # holds a SchemaView, the loaded schema a step reads
    "rdf_persistence_generation/pipeline.py:Run",
    # holds a callable, the function a step runs
    "rdf_persistence_generation/pipeline.py:Step",
    # a dataclass subclass of gen-pydantic's PydanticGenerator, configured by its own fields
    "rdf_persistence_generation/extensions/pydantic_split.py:SplitPydanticGenerator",
    # a dataclass subclass of gen-shacl's ShaclGenerator
    "rdf_persistence_generation/extensions/shacl.py:RpShaclGenerator",
    # holds a SchemaView, the generated classes and an rdflib Graph of the shapes
    "rdf_persistence_generation/testkit/conformance.py:Conformance",
)


# Every turned-on theme is scanned: a stage that turns a theme on needs no edit here (D-13 C2, D-16 C2).
LIBRARY_LAYERS = (*SCANNED_LAYERS, "adapters", "testkit", *sorted(TURNED_ON))
THEME_LAYERS = [
    pytest.param(theme, layer, id=f"{theme}-{layer}")
    for theme in sorted(TURNED_ON)
    for layer in ("domain", "services", "adapters")
    if (REPO / "rdf_persistence" / theme / layer).is_dir()
]


@pytest.mark.parametrize("theme", sorted(TURNED_ON))
def test_the_library_layers_name_every_turned_on_theme(theme):
    assert theme in LIBRARY_LAYERS


@pytest.mark.parametrize(("theme", "layer"), THEME_LAYERS)
def test_a_hand_written_record_in_a_theme_layer_is_caught_by_the_library_layers(
    tmp_path, theme, layer
):
    """The toolkit's own guard call names every turned-on theme: a record planted there is flagged."""
    shutil.copytree(
        REPO / "rdf_persistence",
        tmp_path / "rdf_persistence",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "rdf_persistence" / theme / layer / "handwritten.py").write_text(
        "from pydantic import BaseModel\n\n\nclass Handwritten(BaseModel):\n    x: int\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match=f"{theme}/{layer}/handwritten.py:4"):
        assert_models_generated(
            tmp_path / "rdf_persistence", roots=[], layers=LIBRARY_LAYERS, allow=HAND_WRITTEN
        )


def test_this_repo_has_no_hand_written_model_or_generated_artefact_outside_generated():
    assert_models_generated(
        "rdf_persistence",
        roots=[REPO / "rdf_persistence", REPO / "tests"],
        exempt=[REPO / "tests" / "fixtures"],
        layers=LIBRARY_LAYERS,
        allow=HAND_WRITTEN,
    )
    assert_models_generated(
        REPO / GENERATOR, roots=[REPO / GENERATOR], layers=("",), allow=HAND_WRITTEN
    )


def test_every_hand_written_type_in_the_allow_list_still_exists_and_is_flagged_without_it():
    """An entry that names nothing is dead weight; drop it when the type is generated or gone."""
    flagged = ""
    for package, layers in (("rdf_persistence", LIBRARY_LAYERS), (REPO / GENERATOR, ("",))):
        try:  # the library has no entry left since Conformance moved: nothing may be flagged there
            assert_models_generated(package, roots=[], layers=layers)
        except AssertionError as err:
            flagged += str(err)
    for entry in HAND_WRITTEN:
        path, name = entry.split(":")
        assert f"{path}:" in flagged, f"{entry} is allowed but the guard does not flag it"
        assert f"class {name} " in flagged, f"{entry} is allowed but the guard does not flag it"


def test_the_default_layers_leave_generation_and_testkit_alone_so_consumers_are_unaffected():
    assert SCANNED_LAYERS == ("domain", "services", "entrypoints"), "the consumer default changed"
    assert_models_generated("rdf_persistence", roots=[])
