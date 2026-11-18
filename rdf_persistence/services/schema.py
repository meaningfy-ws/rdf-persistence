"""Open a schema whose metamodel imports resolve to the installed package (PD-22)."""

from importlib import resources
from pathlib import Path

import yaml
from linkml_runtime.utils.schemaview import SchemaView

PACKAGE = "rdf_persistence"
PACKAGE_DIR = Path(str(resources.files(PACKAGE))).resolve()
SERVICE_SCHEMA = PACKAGE_DIR / "model" / "technical" / "service" / "rp_service.yaml"
IRIS_SCHEMA = PACKAGE_DIR / "model" / "technical" / "iris" / "rp_iris_services.yaml"
# The technical schemas whose classes the HTTP API serves, in the order their types and components
# are merged (PD-10): the one place that says what is served. A schema comes before the ones that
# import it, so the types keep the order the single service schema gave them.
SERVED_SCHEMAS = (IRIS_SCHEMA, SERVICE_SCHEMA)
PYTHON_PACKAGE = "python_package"  # the annotation of a toolkit schema: where its code is generated
MODEL_PREFIX = f"{PACKAGE}/model"
# What opening a schema raises when the file or an import is missing, is not YAML, or is not a LinkML
# schema (an unknown field is a TypeError, a missing name a ValueError); any other error is a bug.
LOAD_ERRORS = (OSError, yaml.YAMLError, ValueError, TypeError)


def metamodel_importmap() -> dict[str, str]:
    """Map each ``rdf_persistence/model/<module>`` import to the installed package's module file."""
    model_dir = PACKAGE_DIR / "model"
    return {
        f"{MODEL_PREFIX}/{module.stem}": str(module.with_suffix(""))
        for module in model_dir.glob("*.yaml")
    }


def generated_folder(schema_path: Path) -> Path:
    """The folder of the installed package that holds what was generated from the toolkit schema ``schema_path``.

    Raises:
        KeyError: The schema has no ``python_package`` annotation.
        ValueError: The package is not one of this library's.
    """
    package = str(load_schema(schema_path).schema.annotations[PYTHON_PACKAGE].value)
    root, *parts = package.split(".")
    if root != PACKAGE:
        raise ValueError(f"{package}, the package of {schema_path.name}, is not part of {PACKAGE}")
    return PACKAGE_DIR.joinpath(*parts)


def load_schema(path: str | Path) -> SchemaView:
    """Open the schema at ``path``; ``rdf_persistence/model/<module>`` imports find the package's modules."""
    return SchemaView(str(path), importmap=metamodel_importmap())
