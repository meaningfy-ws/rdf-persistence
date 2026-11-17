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


def _violations(root):
    with pytest.raises(AssertionError) as err:
        assert_models_generated(root / PKG, roots=[])
    return str(err.value)


def test_a_hand_written_model_in_services_is_named(tmp_path):
    _plant(tmp_path, "services/x.py", HAND_WRITTEN)
    found = _violations(tmp_path)
    assert f"{PKG}/services/x.py:" in found, "the file is named"
    assert "X" in found, "the class is named"


@pytest.mark.parametrize(
    "rel", ["services/sub/deeper/x.py", "services/generated.py", "services/generated_x/x.py"]
)
def test_a_hand_written_model_in_services_outside_a_generated_folder_is_named(tmp_path, rel):
    """Row 5: nested folders and names that merely start with `generated` are still scanned."""
    _plant(tmp_path, "__init__.py", "")
    _plant(tmp_path, rel, HAND_WRITTEN)
    assert f"{PKG}/{rel}:" in _violations(tmp_path)


def test_a_hand_written_model_in_services_next_to_the_generated_service_package_is_named(tmp_path):
    """Row 5: a sibling of ``generated/service`` is not exempt."""
    _plant(tmp_path, "__init__.py", "")
    _plant(tmp_path, "services/generated/service/rp_service.py", HAND_WRITTEN)
    _plant(tmp_path, "services/service_models.py", HAND_WRITTEN)
    found = _violations(tmp_path)
    assert f"{PKG}/services/service_models.py:" in found
    assert "generated/service/rp_service.py" not in found


LAZY_INIT = (
    "from importlib import import_module\n"
    "from typing import TYPE_CHECKING\n\n"
    "if TYPE_CHECKING:\n"
    "    from fakepkg.services.generated.service.rp_service import Page\n\n"
    "_LAZY_MODULES = {'Page': 'fakepkg.services.generated.service.rp_service'}\n\n"
    "def __getattr__(name):\n"
    "    return getattr(import_module(_LAZY_MODULES[name]), name)\n"
)


def test_a_class_extending_a_service_model_through_the_lazy_top_level_name_is_named(tmp_path):
    """Found: a subclass reached through a now-lazy top-level name went unseen (D-7).

    The guard reads the lazy exports where they are declared, under ``if TYPE_CHECKING:``.
    """
    _plant(tmp_path, "__init__.py", LAZY_INIT)
    _plant(tmp_path, "services/x.py", "from fakepkg import Page\n\n\nclass P(Page):\n    pass\n")
    assert f"{PKG}/services/x.py:" in _violations(tmp_path)
