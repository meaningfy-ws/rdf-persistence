"""IT-1 of uml-to-linkml: the stage-1 golden passes the lint and boundary steps of ``rp-generate``.

The converter's output is the input of the generator, so the golden (the converted generic library
model) is copied into a project with a ``[tool.rp-generate]`` target and checked with the two steps
that read schemas only. A refusal here is the converter's fault, not the golden's and not the checks'.
"""

import shutil
from pathlib import Path

from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.pipeline import generate
from rdf_persistence_generation.steps import BOUNDARY_STEP, LINT_STEP

GOLDEN = Path(__file__).parents[1] / "fixtures" / "uml" / "golden" / "stage1"
PACKAGE = "uml_app"
PYPROJECT = f"""\
[tool.rp-generate]
schema = "library.yaml"
package = "{PACKAGE}.domain.generated"
python = "{PACKAGE}/domain/generated"
migrations = "migrations"
"""


def test_the_golden_passes_the_lint_and_boundary_steps(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(GOLDEN, project)
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("", encoding="utf-8")
    (project / PACKAGE / "domain" / "__init__.py").write_text("", encoding="utf-8")

    problems = generate(
        read_targets(project / "pyproject.toml"), project, (LINT_STEP, BOUNDARY_STEP), check=True
    )

    assert problems == []
