"""The aggregates of an application's schema: its roots (the tenant root too) and the classes they own."""

from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.checks.scope import (
    aggregate_roots,
    is_tenant_root,
    own_classes,
    own_schemas,
    owned_classes,
)


def root_classes(view: SchemaView, folder: Path) -> list[ClassDefinition]:
    """The aggregate roots and the tenant root of the modules kept in ``folder``, in schema order."""
    classes = own_classes(own_schemas(view, folder))
    roots = {root.name for root in aggregate_roots(view, classes)}
    return [cls for cls in classes if cls.name in roots or is_tenant_root(cls)]


def owned_class_names(view: SchemaView, folder: Path) -> set[str]:
    """The classes the modules kept in ``folder`` reach through ``owned`` slots."""
    return owned_classes(view, own_classes(own_schemas(view, folder)))
