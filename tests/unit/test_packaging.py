"""The built wheel ships the PEP 561 marker, so a consumer's type checker reads our annotations.

Refs: mwb2-adoption-fixes DEC-4 (#42), T-1.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_the_wheel_ships_the_py_typed_marker(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--no-build-isolation", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("*.whl")
    assert "rdf_persistence/py.typed" in zipfile.ZipFile(wheel).namelist(), (
        "the wheel lists the marker"
    )


@pytest.mark.slow
def test_a_consumers_type_checker_reads_our_annotations(tmp_path: Path) -> None:  # T-1b
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        "import rdf_persistence\n"
        "from rdf_persistence import GrantSet\n"
        "from rdf_persistence.testkit import FakeStore\n"
        "\n"
        "GrantSet(grants=5)\n"
    )
    done = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", consumer.name],
        cwd=tmp_path,  # outside the repo: none of its mypy configuration applies
        capture_output=True,
        text=True,
        check=False,
    )
    assert "import-untyped" not in done.stdout, f"the package is typed: {done.stdout}"
    assert "[arg-type]" in done.stdout, f"the wrong argument type is reported: {done.stdout}"
