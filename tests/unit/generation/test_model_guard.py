"""Spec rp-generation: a hand-written domain class is caught, and this repo has none (PD-28)."""

import shutil
from pathlib import Path

import pytest

from rdf_persistence.testkit.guards import assert_models_generated

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


def test_this_repo_has_no_hand_written_model_or_generated_artefact_outside_generated():
    assert_models_generated(
        "rdf_persistence",
        roots=[REPO / "rdf_persistence", REPO / "tests"],
        exempt=[REPO / "tests" / "fixtures"],
    )
