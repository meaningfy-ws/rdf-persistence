"""What ``rp-generate`` says to a converted schema: the lint rules, the boundary check and the dependence check.

``generator_problems`` writes the conversion to a folder as ``rp-uml2linkml`` does and gives the root
schema to the checks that need no generated file (the hard check and the freshness check do).
"""

from pathlib import Path

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation.checks.boundary import boundary_problems
from rdf_persistence_generation.generated.rp_generation import GenerationTarget
from rdf_persistence_generation.pipeline import Run
from rdf_persistence_generation.problems import format_problem
from rdf_persistence_generation.steps import lint_problems
from rdf_persistence_generation.uml.write import write
from tests.generator.uml_model import Converted

ROOT = "app"


def generator_problems(converted: Converted, folder: Path) -> list[str]:
    """The problems of the lint rules and the boundary check (which holds the dependence check), one line each.

    ``folder`` is written to; a conversion with a problem has no schema to check, so it is an error to pass one.
    """
    assert converted.problems == [], converted.problem_texts()
    schemas = folder / "schemas"
    write(list(converted.schemas.values()), converted.report, schemas, ROOT)
    view = load_schema(schemas / f"{ROOT}.yaml")
    target = GenerationTarget(schema=f"{ROOT}.yaml", package="audited.domain.generated")
    linted = lint_problems(Run(target=target, base=schemas, staging=folder / "staging", view=view))
    bounded = boundary_problems(view, schemas)
    return [format_problem(each) for each in [*linted, *bounded]]
