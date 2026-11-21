"""Each theme that owns domain concepts is a generation target of its own (domain-model-per-theme PD-6).

The root ``rp.yaml`` stays the combined target in ``core``; the four theme targets follow it in
``pyproject.toml`` with the keys they need and no more; every module of ``rdf_persistence/model/`` names
the package of its theme in its ``python_package`` annotation, and no YAML file moves.
"""

import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "rdf_persistence" / "model"
CORE = "rdf_persistence.core.domain.generated"


def _package(theme: str) -> str:
    return f"rdf_persistence.{theme}.domain.generated"


# module -> the package its python_package annotation names (PD-6)
ANNOTATIONS = {
    "rp": CORE,
    "rp_core": CORE,
    "rp_annotations": CORE,
    "rp_access": _package("access"),
    "rp_tenancy": _package("access"),
    "rp_provenance": _package("provenance"),
    "rp_files": _package("files"),
    "rp_collections": _package("collaboration"),
    "rp_discussion": _package("collaboration"),
    "rp_workflow": _package("collaboration"),
    "rp_collaboration": _package("collaboration"),
}
THEME_TARGETS = [
    ("rdf_persistence/model/rp_tenancy.yaml", _package("access")),
    ("rdf_persistence/model/rp_provenance.yaml", _package("provenance")),
    ("rdf_persistence/model/rp_files.yaml", _package("files")),
    ("rdf_persistence/model/rp_collaboration.yaml", _package("collaboration")),
]


def _schema(name: str) -> dict:
    return yaml.safe_load((MODEL / f"{name}.yaml").read_text(encoding="utf-8"))


def _targets() -> list[dict]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject["tool"]["rp-generate"]


@pytest.mark.parametrize(("name", "package"), ANNOTATIONS.items())
def test_a_module_names_the_package_of_its_theme(name, package):
    assert _schema(name)["annotations"]["python_package"] == package


def test_the_collaboration_root_imports_its_three_modules_and_nothing_else_of_the_model():
    """PD-6 (DEC-5): a root of its own, so that one target generates the three modules."""
    schema = _schema("rp_collaboration")

    assert schema["id"] == "https://meaningfy.ws/ns/rdf-persistence/collaboration"
    assert schema["name"] == "rp_collaboration"
    assert schema["title"] == "RDF persistence collaboration module"
    assert schema["description"].strip(), "a one-line description"
    assert schema["imports"] == ["linkml:types", "rp_collections", "rp_discussion", "rp_workflow"]
    assert schema["prefixes"] == _schema("rp")["prefixes"], "the prefixes of rp.yaml"
    assert "classes" not in schema, "a root with no classes of its own"
    assert "module_kind" not in schema["annotations"]


def test_the_combined_root_does_not_import_the_collaboration_root():
    assert "rp_collaboration" not in _schema("rp")["imports"]


def test_the_four_theme_targets_follow_the_combined_one_with_only_the_keys_they_need():
    targets = _targets()
    combined = [i for i, t in enumerate(targets) if t["schema"] == "rdf_persistence/model/rp.yaml"]

    assert combined == [0], "rp.yaml is the first target"
    assert targets[0]["package"] == CORE
    for offset, (schema, package) in enumerate(THEME_TARGETS, start=1):
        assert targets[offset] == {
            "schema": schema,
            "package": package,
            "regenerate-command": "make generate",
            "openapi": False,
        }, f"target {offset} should be {schema}"


def test_no_model_file_moved():
    names = {path.name for path in MODEL.glob("*.yaml")}

    assert names == {f"{name}.yaml" for name in ANNOTATIONS}, "the YAML files stay where they are"
