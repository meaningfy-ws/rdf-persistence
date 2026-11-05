"""Open a schema whose metamodel imports resolve to the installed package (PD-22)."""

from importlib import resources
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView

MODEL_PREFIX = "rdf_persistence/model"


def load_schema(path: str | Path) -> SchemaView:
    """Open the schema at ``path``; ``rdf_persistence/model/<module>`` imports find the package's modules."""
    model_dir = Path(str(resources.files("rdf_persistence") / "model"))
    importmap = {
        f"{MODEL_PREFIX}/{module.stem}": str(module.with_suffix(""))
        for module in model_dir.glob("*.yaml")
    }
    return SchemaView(str(path), importmap=importmap)
