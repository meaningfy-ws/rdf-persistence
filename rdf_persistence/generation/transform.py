"""The schema transform that runs before the generators (PD-11)."""

from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.checks.scope import (
    TRUE,
    aggregate_roots,
    annotation,
    is_toolkit_schema,
    own_classes,
    own_schemas,
)


def _set_required(cls: ClassDefinition, slot: str, required: bool) -> None:
    usage = cls.slot_usage.get(slot) or SlotDefinition(name=slot)
    usage.required = required
    cls.slot_usage[slot] = usage


def apply_defaults(view: SchemaView, folder: Path) -> None:
    """Make an unlabelled class's label optional and every aggregate root's description required.

    Only the application's classes change; the toolkit's own schemas are left as they are (PD-23).
    """
    if is_toolkit_schema(folder):
        return
    classes = own_classes(own_schemas(view, folder))
    for cls in classes:
        if annotation(cls, "rp_unlabelled") == TRUE:  # Described gives it the label slot
            _set_required(cls, "label", False)
    for root in aggregate_roots(view, classes):
        _set_required(root, "description", True)
    view.set_modified()
