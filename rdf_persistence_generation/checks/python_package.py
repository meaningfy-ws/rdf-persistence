"""The ``python_package`` rules of the hard check (DEC-7, PD-6): where the toolkit's own modules say they live.

A toolkit run imports a metamodel class from ``<python_package>.<module>``, so every module of the
toolkit's own targets names that package, and it is the package of the target that generates the
module. An application's run only reads the annotations: the toolkit's ``pyproject.toml`` is not in
the wheel, so it has nothing to compare them with.
"""

from collections.abc import Iterator
from pathlib import Path

from linkml_runtime.linkml_model.meta import SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.services.schema_structure import (
    annotation_text,
    is_toolkit_schema,
    own_schemas,
)
from rdf_persistence_generation.config import TOOLKIT_ROOTS
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    GenerationAnnotation,
    HardRule,
)
from rdf_persistence_generation.problems import rule_problem


def python_package_problems(view: SchemaView, folder: Path, package: str) -> list[CheckProblem]:
    """The modules of ``folder`` that name no ``python_package`` or not the target's ``package``; none outside the toolkit."""
    if not is_toolkit_schema(folder, roots=TOOLKIT_ROOTS):
        return []
    return list(_module_problems(own_schemas(view, folder), package))


def _module_problems(schemas: list[SchemaDefinition], package: str) -> Iterator[CheckProblem]:
    tag = GenerationAnnotation.PYTHON_PACKAGE
    for schema in schemas:
        name = str(schema.name)
        declared = annotation_text(schema, tag)
        if declared is None:
            yield rule_problem(
                HardRule.PYTHON_PACKAGE,
                name,
                f"a toolkit module needs the {tag.value} annotation: the package of its target, {package}",
            )
        elif declared != package:
            yield rule_problem(
                HardRule.PYTHON_PACKAGE_MISMATCH,
                name,
                f"{tag.value} is {declared}, but its target generates into {package}",
            )
