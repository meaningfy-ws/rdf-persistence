"""What the checks look at (PD-23): the application's own modules, its roots and its owned classes."""

from collections.abc import Iterator
from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

import rdf_persistence

AGGREGATE_ROOT = "AggregateRoot"
TOOLKIT_DIR = Path(rdf_persistence.__file__).resolve().parent
TRUE = "true"


def annotation_text(element: object, tag: str) -> str | None:
    """The value of the element's annotation ``tag`` as written; None when it has none."""
    annotations = getattr(element, "annotations", None) or {}
    # a class read from the schema holds a dict, an induced slot a JsonObj
    found = (
        annotations.get(tag) if isinstance(annotations, dict) else getattr(annotations, tag, None)
    )
    return None if found is None else str(found.value)


def annotation(element: object, tag: str) -> str | None:
    """The lower-cased value of the element's annotation ``tag``; None when it has none."""
    text = annotation_text(element, tag)
    return None if text is None else text.lower()


def is_toolkit_schema(folder: Path) -> bool:
    """True for the toolkit's own schemas, which PD-23 exempts from the class-level rules."""
    return folder.resolve().is_relative_to(TOOLKIT_DIR)


def own_schemas(view: SchemaView, folder: Path) -> list[SchemaDefinition]:
    """The modules of the closure kept in ``folder``, beside the root schema (not the metamodel's)."""
    view.imports_closure()
    return [
        schema
        for schema in view.schema_map.values()
        if schema.source_file and Path(schema.source_file).resolve().parent == folder.resolve()
    ]


def own_classes(schemas: list[SchemaDefinition]) -> list[ClassDefinition]:
    return [cls for schema in schemas for cls in schema.classes.values()]


def declared_slots(cls: ClassDefinition) -> set[str]:
    """The slots a class declares or narrows itself, as opposed to the ones it inherits."""
    return {*cls.slots, *cls.attributes, *cls.slot_usage}


def aggregate_roots(view: SchemaView, classes: list[ClassDefinition]) -> list[ClassDefinition]:
    """The concrete classes whose induced ancestors include ``AggregateRoot``."""
    return [
        cls
        for cls in classes
        if not cls.mixin and not cls.abstract and AGGREGATE_ROOT in view.class_ancestors(cls.name)
    ]


def is_tenant_root(cls: ClassDefinition) -> bool:
    """The tenant's root object lives in the meta graph and needs no path (PD-8)."""
    return annotation(cls, "graph") == "meta"


def owned_slots(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[tuple[str, str]]:
    """``(slot, range)`` of each declared slot marked ``owned: true`` whose range is a class."""
    for cls in classes:
        induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
        for name in sorted(declared_slots(cls) & induced.keys()):
            slot = induced[name]
            if annotation(slot, "owned") == TRUE and slot.range in view.all_classes():
                yield name, slot.range


def owned_classes(view: SchemaView, classes: list[ClassDefinition]) -> set[str]:
    """The classes reached through ``owned`` slots, with their subclasses."""
    return {
        owned
        for _, range_ in owned_slots(view, classes)
        for owned in view.class_descendants(range_)
    }


def inherits_from_metamodel(view: SchemaView, cls: ClassDefinition, own: set[str]) -> bool:
    """True when an ``is_a`` ancestor of ``cls`` is not the application's own (PD-23 exempts it)."""
    return any(name not in own for name in view.class_ancestors(cls.name, mixins=False)[1:])
