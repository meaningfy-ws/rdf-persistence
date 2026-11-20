"""IT-1 of uml-to-linkml: the goldens pass the checks of ``rp-generate``.

The converter's output is the input of the generator, so a golden (the converted generic library model)
is copied into a project with a ``[tool.rp-generate]`` target and checked with the steps that read
schemas only: lint and boundary for stage 1, lint, boundary, hard and rules for stage 2. A refusal here
is the converter's fault, not the golden's and not the checks'.
"""

import shutil
from pathlib import Path

from linkml_runtime.dumpers import yaml_dumper

from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.pipeline import generate
from rdf_persistence_generation.steps import BOUNDARY_STEP, HARD_STEP, LINT_STEP, RULES_STEP
from tests.generator.uml_model import BOOK, CHAPTER, SERIES, attribute, klass, model, run

GOLDEN = Path(__file__).parents[1] / "fixtures" / "uml" / "golden" / "stage1"
GOLDEN_STAGE_2 = Path(__file__).parents[1] / "fixtures" / "uml" / "golden" / "stage2"
PACKAGE = "uml_app"
PYPROJECT = f"""\
[tool.rp-generate]
schema = "library.yaml"
package = "{PACKAGE}.domain.generated"
python = "{PACKAGE}/domain/generated"
migrations = "migrations"
"""


def _project_of(golden: Path, tmp_path: Path) -> Path:
    """A project folder holding a golden's files and a ``[tool.rp-generate]`` target."""
    project = tmp_path / "project"
    shutil.copytree(golden, project)
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("", encoding="utf-8")
    (project / PACKAGE / "domain" / "__init__.py").write_text("", encoding="utf-8")
    return project


def test_the_golden_passes_the_lint_and_boundary_steps(tmp_path: Path) -> None:
    project = _project_of(GOLDEN, tmp_path)

    problems = generate(
        read_targets(project / "pyproject.toml"), project, (LINT_STEP, BOUNDARY_STEP), check=True
    )

    assert problems == [], "the stage-1 golden must pass the lint and the boundary check"


def test_the_stage_two_golden_passes_lint_boundary_hard_and_rules(tmp_path: Path) -> None:
    project = _project_of(GOLDEN_STAGE_2, tmp_path)

    problems = generate(
        read_targets(project / "pyproject.toml"),
        project,
        (LINT_STEP, BOUNDARY_STEP, HARD_STEP, RULES_STEP),
        check=True,
    )

    assert problems == [], "the stage-2 golden must pass all four checks of rp-generate"


def test_a_shared_slot_whose_usages_disagree_on_description_passes_the_lint(
    tmp_path: Path,
) -> None:
    uml = model(
        klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, "lib:isbn", note="The isbn."),)),
        klass(
            SERIES, "lib:Series", attributes=(attribute(2, SERIES, "lib:isbn", note="The code."),)
        ),
        klass(CHAPTER, "lib:Chapter", attributes=(attribute(3, CHAPTER, "lib:isbn", note=None),)),
    )
    converted = run(uml, root_name="library")
    assert converted.problems == [], converted.problem_texts()
    project = tmp_path / "project"
    project.mkdir()
    for schema in converted.schemas.values():
        yaml_dumper.dump(schema, str(project / f"{schema.name}.yaml"))
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("", encoding="utf-8")
    (project / PACKAGE / "domain" / "__init__.py").write_text("", encoding="utf-8")

    problems = generate(read_targets(project / "pyproject.toml"), project, (LINT_STEP,), check=True)

    assert problems == [], "the shared slot must keep a description for the lint"
