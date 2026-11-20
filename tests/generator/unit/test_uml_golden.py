"""TC-11: the goldens of ``rp-uml2linkml`` (PD-22, I-2).

Two generic library models are converted through the command into a folder: the stage-1 model of
``tests/generator/uml_library.py`` and the stage-2 model of ``tests/generator/uml_library_stage2.py``
(the design's worked example with an activity root, a tenant root, an abstract root and a slot shared
across packages). The files, the report included, equal the golden under ``fixtures/uml/golden/<stage>/``
as exact text and exact file set, and a second run writes the same bytes. A golden is rewritten only when
``RP_REFRESH_GOLDEN`` is set (``make refresh-golden``); a plain run never writes it.
"""

import os
from pathlib import Path
from types import ModuleType

import pytest

from rdf_persistence_generation.uml.cli import main
from tests.generator import uml_library, uml_library_stage2

GOLDENS = Path(__file__).parents[1] / "fixtures" / "uml" / "golden"
REFRESH_VARIABLE = "RP_REFRESH_GOLDEN"
MODELS: dict[str, ModuleType] = {"stage1": uml_library, "stage2": uml_library_stage2}


def convert_library(stage: str, folder: Path, out: Path) -> None:
    """Run the command over the library model of ``stage`` in ``folder`` (built once), into ``out``; exit 0."""
    model = MODELS[stage]
    qea = folder / "library.qea"
    code = main(
        [
            str(qea if qea.exists() else model.build_library(folder)),
            "--package",
            model.PACKAGE,
            "--prefixes",
            str(model.write_prefixes(folder)),
            "--out",
            str(out),
            "--root-name",
            model.ROOT_NAME,
        ]
    )
    assert code == 0, f"the {stage} library must convert without a problem"


def files_of(folder: Path) -> dict[str, str]:
    return {file.name: file.read_text(encoding="utf-8") for file in sorted(folder.iterdir())}


def _refresh(golden: Path, produced: dict[str, str]) -> None:
    golden.mkdir(parents=True, exist_ok=True)
    for old in golden.iterdir():
        old.unlink()
    for name, text in produced.items():
        (golden / name).write_text(text, encoding="utf-8")


@pytest.mark.parametrize("stage", sorted(MODELS))
def test_the_output_equals_the_golden(stage: str, tmp_path: Path) -> None:
    out = tmp_path / "out"
    convert_library(stage, tmp_path, out)
    produced = files_of(out)
    golden_folder = GOLDENS / stage
    if os.environ.get(REFRESH_VARIABLE):
        _refresh(golden_folder, produced)

    golden = files_of(golden_folder)

    assert sorted(produced) == sorted(golden), f"the {stage} file set differs from the golden one"
    for name, text in produced.items():
        assert text == golden[name], f"{stage}/{name} differs from the golden text"


@pytest.mark.parametrize("stage", sorted(MODELS))
def test_a_second_run_writes_the_same_bytes(stage: str, tmp_path: Path) -> None:
    out = tmp_path / "out"
    convert_library(stage, tmp_path, out)
    first = {file.name: file.read_bytes() for file in sorted(out.iterdir())}

    convert_library(stage, tmp_path, out)

    assert {file.name: file.read_bytes() for file in sorted(out.iterdir())} == first, (
        f"a second {stage} run must write the same bytes"
    )
