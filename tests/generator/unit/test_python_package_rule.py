"""The ``python_package`` rules end to end through ``rp-generate`` (generator-package stage 3, DEC-7, PD-6)."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation import steps
from rdf_persistence_generation.cli import main
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.generated.rp_generation import HardRule
from rdf_persistence_generation.pipeline import generate
from rdf_persistence_generation.problems import format_problem

from .conftest import ROOT_SCHEMA

METAMODEL_DIR = Path(__file__).parents[3] / "rdf_persistence" / "model"
TOOLKIT_DOMAIN = "rdf_persistence.core.domain.generated"
PACKAGE_RULES = {HardRule.PYTHON_PACKAGE.value, HardRule.PYTHON_PACKAGE_MISMATCH.value}
ROOTS_USERS = (
    "rdf_persistence_generation.config",
    "rdf_persistence_generation.checks.python_package",
    "rdf_persistence_generation.checks.hard",
    "rdf_persistence_generation.checks.boundary",
    "rdf_persistence_generation.components",
    "rdf_persistence_generation.lock_step",
    "rdf_persistence_generation.extensions.shacl",
    "rdf_persistence_generation.extensions.typescript",
    "rdf_persistence_generation.extensions.pydantic_split",
)
CONSUMER_ANNOTATION = "python_package: somewhere.else"

Edit = Callable[[str, str, str], None]


@pytest.fixture
def toolkit_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project folder holding a copy of the metamodel, treated as the toolkit's own, and a pyproject for it."""
    shutil.copytree(
        METAMODEL_DIR,
        tmp_path / "model",
        ignore=shutil.ignore_patterns("migrations", "__pycache__", "generated"),
    )
    for module in ROOTS_USERS:
        monkeypatch.setattr(f"{module}.TOOLKIT_ROOTS", (tmp_path.resolve(),))
    (tmp_path / "pyproject.toml").write_text(
        f'[[tool.rp-generate]]\nschema = "model/rp.yaml"\npackage = "{TOOLKIT_DOMAIN}"\n'
        'regenerate-command = "make generate"\nopenapi = false\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def edit(toolkit_project: Path) -> Edit:
    def apply(module: str, old: str, new: str) -> None:
        path = toolkit_project / "model" / f"{module}.yaml"
        text = path.read_text(encoding="utf-8")
        assert old in text, f"{old!r} is not in {module}"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    return apply


def _declare_consumer_package(folder: Path) -> None:
    path = folder / ROOT_SCHEMA
    text = path.read_text(encoding="utf-8")
    if "\nannotations:" in text:
        text = text.replace("\nannotations:", f"\nannotations:\n  {CONSUMER_ANNOTATION}", 1)
    else:
        text += f"\nannotations:\n  {CONSUMER_ANNOTATION}\n"
    path.write_text(text, encoding="utf-8")


def test_rp_generate_refuses_a_module_without_python_package_and_writes_nothing(
    toolkit_project: Path, edit: Edit, capsys: pytest.CaptureFixture[str]
) -> None:
    """Error matrix: a metamodel module lacks python_package."""
    edit("rp_files", f"python_package: {TOOLKIT_DOMAIN}", "unrelated: note")
    code = main(["--project", str(toolkit_project / "pyproject.toml")])
    err = capsys.readouterr().err
    assert code == 1, f"exit code; stderr was {err}"
    assert "rp_files" in err and "python_package" in err, "the module and the annotation are named"  # noqa: PT018
    assert sorted(p.name for p in toolkit_project.iterdir()) == ["model", "pyproject.toml"], (
        "nothing written, no staging folder left"
    )


def test_rp_generate_refuses_a_disagreeing_package_naming_both_values_and_writes_nothing(
    toolkit_project: Path, edit: Edit, capsys: pytest.CaptureFixture[str]
) -> None:
    """Error matrix: python_package disagrees with the toolkit target's package."""
    edit("rp_core", f"python_package: {TOOLKIT_DOMAIN}", "python_package: x.generated")
    code = main(["--project", str(toolkit_project / "pyproject.toml")])
    err = capsys.readouterr().err
    assert code == 1, f"exit code; stderr was {err}"
    for named in ("rp_core", "x.generated", TOOLKIT_DOMAIN):
        assert named in err, f"{named} is named"
    assert sorted(p.name for p in toolkit_project.iterdir()) == ["model", "pyproject.toml"], (
        "nothing written"
    )


def test_a_consumer_python_package_is_never_checked_and_leaves_the_output_unchanged(
    toy_copy: Path, tmp_path: Path
) -> None:
    """TC-37 (consumer half): a consumer's own python_package is neither required nor compared (PD-6)."""
    target = read_targets(toy_copy / "pyproject.toml")[0]

    def render(folder: Path) -> dict[str, str]:
        out = tmp_path / folder.name
        steps.PYTHON_STEP.run(steps.Run(target, folder, out, load_schema(folder / ROOT_SCHEMA)))
        return {str(p.relative_to(out)): p.read_text(encoding="utf-8") for p in out.rglob("*.py")}

    before = render(toy_copy)
    _declare_consumer_package(toy_copy)
    found = generate([target], toy_copy, (steps.HARD_STEP,), check=True)
    assert [format_problem(p) for p in found if p.rule in PACKAGE_RULES] == [], "no rule fires"
    assert render(toy_copy) == before, "the consumer's python_package changed generated code"
