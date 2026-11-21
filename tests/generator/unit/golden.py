"""Golden comparison for the extension tests (PD-25, PD-27 item 2).

The golden of the toy library is the committed generated tree itself (``tests/fixtures/library/
domain/generated`` and ``.../web/src/domain/generated``): a test renders one extension's output afresh and
compares it with that tree, so there is no second copy to keep in step. Turtle is compared by
meaning, everything else (JSON too) by exact text, and the file set must match exactly. A mismatch
means the tree is stale: ``make generate`` rewrites it.

A schema that is not the toy has no committed tree, so it keeps a golden folder under
``fixtures/library/golden``. Those are rewritten only when ``RP_REFRESH_GOLDEN`` is set (``make
refresh-golden`` sets it); a plain test run never writes them.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic, to_isomorphic

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation.cli import main
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.generated.rp_generation import GenerationManifest, GenerationTarget
from rdf_persistence_generation.pipeline import Run, Step

TOY = Path(__file__).parents[2] / "fixtures" / "library"
ROOT_SCHEMA = "library.yaml"

Breaker = Callable[[str, str, str], Path]

GOLDEN_ROOT = TOY / "golden"
REFRESH_VARIABLE = "RP_REFRESH_GOLDEN"
TURTLE = ".ttl"
PYTHON = ".py"
KEPT_AS = ".golden"  # a Python golden is kept as text, so no tool lints, types or imports it
TOY_TARGET = read_targets(TOY / "pyproject.toml")[0]
STALE_TREE = (
    "the committed tree differs from a fresh render: run `make generate` and review the diff"
)

# --- the small generated project the generator's CLI, freshness and plugin tests share ----------

PYPROJECT = """
[tool.rp-generate]
schema = "m.yaml"
package = "app.domain.generated"
migrations = "migrations"
"""

SCHEMA = """
id: https://example.org/ns/m
name: m
title: Module
version: "1"
description: A module for the tests.
prefixes:
  tst: https://example.org/ns/m#
  linkml: https://w3id.org/linkml/
default_prefix: tst
default_range: string
imports:
  - linkml:types
  - rdf_persistence/model/rp_core
  - rdf_persistence/model/rp_annotations
classes:
  Thing:
    title: Thing
    description: A thing.
    mixins: [AggregateRoot, Described]
    annotations:
      rp_path: things
"""

DEFAULT_HINT = "run `rp-generate` to regenerate, then commit the result"
MANIFEST = Path("app/domain/generated/rp-manifest.json")
NAMED = 'regenerate-command = "make generate-models"\n'
TEST = "def test_it():\n    assert True\n"
INI = "[pytest]\nrp_generate_projects =\n    pyproject.toml\n    other/pyproject.toml\n"


def project(tmp_path: Path, schema: str = SCHEMA, pyproject: str = PYPROJECT) -> Path:
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (tmp_path / "m.yaml").write_text(schema, encoding="utf-8")
    return tmp_path / "pyproject.toml"


def make_project(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (folder / "m.yaml").write_text(SCHEMA, encoding="utf-8")
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the project must generate"
    return folder


def read_manifest(pyproject: Path) -> GenerationManifest:
    return GenerationManifest.model_validate_json(
        (pyproject.parent / MANIFEST).read_text(encoding="utf-8")
    )


def check(pyproject: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    capsys.readouterr()
    code = main(["--project", str(pyproject), "--check"])
    return code, capsys.readouterr().err


def run_toy(step: Step, staging: Path, target: GenerationTarget = TOY_TARGET) -> Path:
    """Run ``step`` over the toy library, writing into ``staging`` the way a real run would; returns ``staging``."""
    step.run(Run(target, TOY, staging, load_schema(TOY / ROOT_SCHEMA)))
    return staging


def _files(folder: Path) -> list[Path]:
    return sorted(p.relative_to(folder) for p in folder.rglob("*") if p.is_file())


def _turtle_difference(produced: Path, golden: Path) -> str | None:
    """None when the two Turtle files are the same graph; otherwise the triples only one has."""
    left, right = Graph().parse(produced), Graph().parse(golden)
    if isomorphic(left, right):
        return None
    _, only_golden, only_produced = graph_diff(to_isomorphic(right), to_isomorphic(left))
    return (
        f"only in the golden:\n{only_golden.serialize(format='turtle')}\n"
        f"only in the produced:\n{only_produced.serialize(format='turtle')}"
    )


def _assert_same(label: str, produced: Path, golden: Path) -> None:
    if produced.suffix == TURTLE:
        difference = _turtle_difference(produced, golden)
        assert difference is None, f"{label} differs as RDF:\n{difference}"
    else:
        assert produced.read_text(encoding="utf-8") == golden.read_text(encoding="utf-8"), (
            f"{label} differs from the golden text"
        )


def assert_matches_toy(produced: Path, *patterns: str) -> None:
    """Fail unless ``produced`` holds exactly the committed toy files that ``patterns`` select, each equal.

    ``patterns`` are globs relative to the toy folder (``domain/generated/*.py``); ``produced`` is the
    staging folder of a step run laid out the way the toy's folders are.
    """
    committed = sorted({p.relative_to(TOY) for pattern in patterns for p in TOY.glob(pattern)})
    assert _files(produced) == committed, f"the produced file set differs. {STALE_TREE}"
    for name in committed:
        _assert_same(f"{name}", produced / name, TOY / name)


# --- goldens of schemas that are not the toy ----------------------------------------------------


def stored(name: Path) -> Path:
    """The name a golden is kept under: a Python file gets a ``.golden`` suffix."""
    return name.with_name(name.name + KEPT_AS) if name.suffix == PYTHON else name


def _golden_names(golden: Path) -> list[Path]:
    """The golden files of a folder under the names they stand for."""
    return sorted(
        p.with_name(p.name.removesuffix(KEPT_AS)) if p.suffix == KEPT_AS else p
        for p in _files(golden)
    )


def _refresh(produced: Path, golden: Path, names: list[Path]) -> None:
    for old in _files(golden) if golden.exists() else []:
        (golden / old).unlink()
    for name in names:
        (golden / stored(name)).parent.mkdir(parents=True, exist_ok=True)
        (golden / stored(name)).write_bytes((produced / name).read_bytes())


def assert_matches_golden(name: str, produced: Path) -> None:
    """Fail unless ``produced`` holds exactly the files of ``golden/<name>/``, each equal by kind."""
    golden = GOLDEN_ROOT / name
    names = _files(produced)
    if os.environ.get(REFRESH_VARIABLE):
        _refresh(produced, golden, names)
    expected = _golden_names(golden) if golden.exists() else []
    assert names == expected, f"{name}: the produced file set differs from the golden one"
    for file in names:
        _assert_same(f"{name}/{file}", produced / file, golden / stored(file))
