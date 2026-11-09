"""The built wheel ships the PEP 561 marker, so a consumer's type checker reads our annotations.

Refs: mwb2-adoption-fixes DEC-4 (#42), T-1.
"""

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_wheel_ships_the_py_typed_marker(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--no-build-isolation", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("*.whl")
    assert "rdf_persistence/py.typed" in zipfile.ZipFile(wheel).namelist()
