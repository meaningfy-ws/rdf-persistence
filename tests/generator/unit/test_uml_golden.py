"""TC-11: the stage-1 golden of ``rp-uml2linkml`` (PD-22, I-2).

The generic library model of ``tests/generator/uml_library.py`` is converted through the command into a
folder; the files, the report included, equal the golden under ``fixtures/uml/golden/stage1/`` as exact
text and exact file set, and a second run writes the same bytes. The golden is rewritten only when
``RP_REFRESH_GOLDEN`` is set (``make refresh-golden``); a plain run never writes it.
"""

import os
from pathlib import Path

from rdf_persistence_generation.uml.cli import main
from tests.generator.uml_library import PACKAGE, ROOT_NAME, build_library, write_prefixes

GOLDEN = Path(__file__).parents[1] / "fixtures" / "uml" / "golden" / "stage1"
REFRESH_VARIABLE = "RP_REFRESH_GOLDEN"


def convert_library(folder: Path, out: Path) -> None:
    """Run the command over the library model of ``folder`` (built once), into ``out``; exit 0."""
    qea = folder / "library.qea"
    code = main(
        [
            str(qea if qea.exists() else build_library(folder)),
            "--package",
            PACKAGE,
            "--prefixes",
            str(write_prefixes(folder)),
            "--out",
            str(out),
            "--root-name",
            ROOT_NAME,
        ]
    )
    assert code == 0, f"the conversion of the library exits {code}"


def files_of(folder: Path) -> dict[str, str]:
    return {file.name: file.read_text(encoding="utf-8") for file in sorted(folder.iterdir())}


def _refresh(produced: dict[str, str]) -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for old in GOLDEN.iterdir():
        old.unlink()
    for name, text in produced.items():
        (GOLDEN / name).write_text(text, encoding="utf-8")


def test_the_stage_one_output_equals_the_golden(tmp_path: Path) -> None:
    out = tmp_path / "out"
    convert_library(tmp_path, out)
    produced = files_of(out)
    if os.environ.get(REFRESH_VARIABLE):
        _refresh(produced)

    golden = files_of(GOLDEN)

    assert sorted(produced) == sorted(golden), "the produced file set differs from the golden one"
    for name, text in produced.items():
        assert text == golden[name], f"{name} differs from the golden text"


def test_a_second_run_writes_the_same_bytes(tmp_path: Path) -> None:
    out = tmp_path / "out"
    convert_library(tmp_path, out)
    first = {file.name: file.read_bytes() for file in sorted(out.iterdir())}

    convert_library(tmp_path, out)

    assert {file.name: file.read_bytes() for file in sorted(out.iterdir())} == first, (
        "the second run writes other bytes"
    )
