"""Run one pipeline step over the toy library, and compare JSON output with its golden folder (PD-25)."""

import json
import os
from pathlib import Path

from rdf_persistence.generation.generated.rp_generation import GenerationTarget
from rdf_persistence.generation.pipeline import Run, Step
from rdf_persistence.services.schema import load_schema

from .conftest import ROOT_SCHEMA, TOY
from .golden import GOLDEN_ROOT, REFRESH_VARIABLE

TARGET = GenerationTarget(
    schema_file=ROOT_SCHEMA,
    package="tests.fixtures.library.generated",
    python="python",
    typescript="typescript",
    diagrams="diagrams",
)


def run_toy(step: Step, staging: Path, target: GenerationTarget = TARGET) -> Path:
    """Run ``step`` over the toy library, writing into ``staging``; returns ``staging``."""
    step.run(Run(target, TOY, staging, load_schema(TOY / ROOT_SCHEMA)))
    return staging


def _names(folder: Path) -> list[Path]:
    return sorted(p.relative_to(folder) for p in folder.rglob("*") if p.is_file())


def assert_json_golden(module: str, produced: Path) -> None:
    """Fail unless ``produced`` holds exactly the files of ``golden/<module>/``, each equal once parsed."""
    golden = GOLDEN_ROOT / module
    names = _names(produced)
    if os.environ.get(REFRESH_VARIABLE):
        for old in _names(golden) if golden.exists() else []:
            (golden / old).unlink()
        for name in names:
            (golden / name).parent.mkdir(parents=True, exist_ok=True)
            (golden / name).write_bytes((produced / name).read_bytes())
    assert names == (_names(golden) if golden.exists() else []), f"{module}: the file set differs"
    for name in names:
        left = json.loads((produced / name).read_text(encoding="utf-8"))
        right = json.loads((golden / name).read_text(encoding="utf-8"))
        assert left == right, f"{module}/{name} differs from its golden"
