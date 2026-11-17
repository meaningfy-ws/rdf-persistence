"""The model guard over the moved technical models: generated ones pass, a hand-written one is named (TC-11, PD-3)."""

import pytest

from rdf_persistence.testkit.guards import assert_models_generated

PKG = "fakepkg"
HAND_WRITTEN = "from rdf_persistence.domain.base import RpModel\n\n\nclass X(RpModel):\n    pass\n"


def _plant(root, rel, text):
    path = root / PKG / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_toolkit_tree_has_no_hand_written_model_with_the_service_models_under_services():
    assert_models_generated("rdf_persistence", roots=[])


def test_a_model_class_under_services_generated_is_not_flagged(tmp_path):
    _plant(tmp_path, "services/generated/service/rp_service.py", HAND_WRITTEN)
    assert assert_models_generated(tmp_path / PKG, roots=[]) is None, (
        "generated folders are skipped"
    )


def test_a_hand_written_model_in_services_is_named(tmp_path):
    _plant(tmp_path, "services/x.py", HAND_WRITTEN)
    with pytest.raises(AssertionError) as err:
        assert_models_generated(tmp_path / PKG, roots=[])
    assert f"{PKG}/services/x.py:" in str(err.value), "the file is named"
    assert "X" in str(err.value), "the class is named"
