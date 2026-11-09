"""Step 6 of ``howto/adopt.adoc`` is true: its code uses public names only and runs (PD-4, T-12, T-15).

The tests read the guide's own listing blocks, so the guide and the tests cannot drift.
"""

import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from rdf_persistence.testkit import assert_public_imports

ROOT = Path(__file__).parents[3]
GUIDE = ROOT / "docs" / "modules" / "ROOT" / "pages" / "howto" / "adopt.adoc"
FIXTURES = ROOT / "tests" / "fixtures"
CONSUMER_FILE = "# tests/test_model.py"
LISTING = re.compile(r"\[source,python\]\n----\n(.*?)\n----", re.DOTALL)


def step_6_test_model() -> str:
    """The code of every listing of step 6 that belongs to the consumer's ``tests/test_model.py``."""
    text = GUIDE.read_text(encoding="utf-8")
    step = text.split("[#guard]", 1)[1].split("\n== 7.", 1)[0]
    blocks = [b for b in LISTING.findall(step) if b.startswith(CONSUMER_FILE)]
    assert len(blocks) == 2, "step 6 shows the model tests and the fifth check, two listings"
    return "\n\n".join(blocks)


def test_the_step_6_imports_are_public(tmp_path: Path) -> None:
    written = tmp_path / "test_model.py"
    written.write_text(step_6_test_model(), encoding="utf-8")
    assert_public_imports(written)


def test_a_testkit_module_import_is_refused_naming_file_line_and_module(tmp_path: Path) -> None:
    written = tmp_path / "test_model.py"
    written.write_text(
        "import os\nfrom rdf_persistence.testkit.strategies import aggregate\n", encoding="utf-8"
    )
    with pytest.raises(AssertionError) as err:
        assert_public_imports(written)
    assert "test_model.py:2 imports rdf_persistence.testkit.strategies" in str(err.value)


@pytest.fixture
def guide_namespace(tmp_path: Path) -> dict[str, Any]:
    """Step 6 run as a consumer's ``tests/test_model.py``: the toy library laid out as the guide says."""
    shutil.copytree(FIXTURES / "library", tmp_path / "models", ignore=shutil.ignore_patterns("web"))
    shutil.copytree(FIXTURES / "conformance", tmp_path / "tests" / "conformance")
    (tmp_path / "library").mkdir()  # the guide's package folder, for the hand-written-model scan
    # a real file: Hypothesis reads the source of tests
    written = tmp_path / "tests" / "test_model.py"
    written.write_text(step_6_test_model(), encoding="utf-8")
    namespace: dict[str, Any] = {"__file__": str(written)}
    exec(compile(written.read_text(encoding="utf-8"), str(written), "exec"), namespace)
    return namespace


@pytest.mark.parametrize(
    "check",
    [
        "test_no_hand_written_models",
        "test_classes_and_shapes_agree",
        "test_a_book_survives_the_round_trip",
        "test_the_generated_classes_follow_the_schema",
    ],
)
def test_the_guides_checks_pass_on_the_toy_library(
    guide_namespace: dict[str, Any], check: str
) -> None:
    guide_namespace[check]()


def test_the_guides_snapshot_check_needs_a_deliberate_refresh(
    guide_namespace: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    check = guide_namespace["test_the_model_shape_is_the_reviewed_one"]
    monkeypatch.delenv("REFRESH_SNAPSHOT", raising=False)
    with pytest.raises(FileNotFoundError):
        check()  # no reviewed snapshot yet
    monkeypatch.setenv("REFRESH_SNAPSHOT", "1")
    check()  # the deliberate refresh writes it
    monkeypatch.delenv("REFRESH_SNAPSHOT")
    check()  # and the shape is then the reviewed one
