"""Open a schema whose metamodel imports resolve to the installed package (PD-22)."""

from importlib import resources
from pathlib import Path

import yaml
from linkml_runtime.utils.schemaview import SchemaView

PACKAGE = "rdf_persistence"
PACKAGE_DIR = Path(str(resources.files(PACKAGE))).resolve()
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


def load_schema(path: str | Path) -> SchemaView:
    """Open the schema at ``path``; ``rdf_persistence/model/<module>`` imports find the package's modules."""
    return SchemaView(str(path), importmap=metamodel_importmap())
