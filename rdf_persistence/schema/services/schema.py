"""Open a schema whose metamodel imports resolve to the installed package (PD-22)."""

from collections.abc import Iterator
from copy import deepcopy
from importlib import resources
from pathlib import Path

import yaml
from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

PACKAGE = "rdf_persistence"
AGGREGATE_ROOT = "AggregateRoot"  # the mixin that makes a class an aggregate root
PACKAGE_DIR = Path(str(resources.files(PACKAGE))).resolve()
API_ENTRYPOINTS_SCHEMA = PACKAGE_DIR / "model" / "technical" / "api" / "rp_api_entrypoints.yaml"
IRIS_SCHEMA = PACKAGE_DIR / "model" / "technical" / "iris" / "rp_iris_services.yaml"
# The technical schemas whose classes the HTTP API serves, in the order their types and components
# are merged (PD-10): the one place that says what is served. A schema comes before the ones that
# import it, so the types keep the order the single service schema gave them.
PERSISTENCE_SCHEMA = (
    PACKAGE_DIR / "model" / "technical" / "persistence" / "rp_persistence_services.yaml"
)
MIGRATIONS_SCHEMA = (
    PACKAGE_DIR / "model" / "technical" / "migrations" / "rp_migrations_services.yaml"
)
ACCESS_SCHEMA = PACKAGE_DIR / "model" / "technical" / "access" / "rp_access_services.yaml"
TENANCY_SCHEMA = PACKAGE_DIR / "model" / "technical" / "tenancy" / "rp_tenancy_services.yaml"
EVENTS_SCHEMA = PACKAGE_DIR / "model" / "technical" / "events" / "rp_events_services.yaml"
COLLABORATION_SCHEMA = (
    PACKAGE_DIR / "model" / "technical" / "collaboration" / "rp_collaboration_services.yaml"
)
SERVED_SCHEMAS = (
    IRIS_SCHEMA,
    PERSISTENCE_SCHEMA,
    MIGRATIONS_SCHEMA,
    ACCESS_SCHEMA,
    TENANCY_SCHEMA,
    EVENTS_SCHEMA,
    COLLABORATION_SCHEMA,
    API_ENTRYPOINTS_SCHEMA,
)
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
    """Open the schema at ``path``; ``rdf_persistence/model/<module>`` imports find the package's modules.

    An application slot named like a toolkit slot that no toolkit class carries wins over it
    (``prefer_application_slots``), whatever the order of the imports. An abstract aggregate root
    names the identifier of its kinds (``give_identifier_to_abstract_roots``), so a slot over it is
    a reference for every reader (#303).
    """
    view = SchemaView(str(path), importmap=metamodel_importmap())
    prefer_application_slots(view)
    give_identifier_to_abstract_roots(view)
    return view


def give_identifier_to_abstract_roots(view: SchemaView) -> None:
    """Let each abstract aggregate root of the application declare the identifier its kinds carry.

    A class with no identifier reads as having no reference to point at, so a slot over it is
    inlined in the stock generators, in ``SchemaView.is_inlined`` and in the mapper alike
    (DEC-6, #303). A root is a reference whether its range is abstract or concrete, so the abstract
    root takes the identifier slot of its concrete descendants. The module is copied first; the
    loaded module may be shared.

    An abstract root with no descendant that has an identifier is left as it is: there is nothing to
    point at. Descendants whose identifier slots differ cannot share one reference, so the root is
    refused.

    Raises:
        ValueError: The descendants of an abstract root carry identifier slots of different names;
            the message names the class and the slots.
    """
    view.imports_closure()
    for key, module in list(view.schema_map.items()):
        if is_toolkit_module(module):
            continue
        found = {
            name: names
            for name, cls in module.classes.items()
            if (names := _kinds_identifier(view, cls))
        }
        if not found:
            continue
        copy = deepcopy(module)
        for name, names in found.items():
            if len(names) > 1:
                raise ValueError(
                    f"{name} is an abstract aggregate root whose kinds have different identifier "
                    f"slots, {sorted(names)}; give them one"
                )
            copy.classes[name].slots.append(next(iter(names)))
        view.schema_map[key] = copy
        view.set_modified()


def _kinds_identifier(view: SchemaView, cls: ClassDefinition) -> set[str]:
    """The names of the identifier slots of the kinds of an abstract root with none of its own."""
    if not cls.abstract or cls.mixin or AGGREGATE_ROOT not in view.class_ancestors(cls.name):
        return set()
    if view.get_identifier_slot(cls.name) is not None:
        return set()
    identifiers = (
        view.get_identifier_slot(name) for name in view.class_descendants(cls.name, reflexive=False)
    )
    return {slot.name for slot in identifiers if slot is not None}


def is_toolkit_module(schema: SchemaDefinition) -> bool:
    """True for a module of the toolkit's metamodel, as opposed to one of the application."""
    source = schema.source_file
    return bool(source) and Path(str(source)).resolve().is_relative_to(PACKAGE_DIR / "model")


def slot_iri(view: SchemaView, schema: SchemaDefinition, slot: SlotDefinition) -> str:
    """The expanded IRI of ``slot`` as its own module defines it, never as a merged view resolves its name."""
    return str(view.expand_curie(str(slot.slot_uri or f"{schema.default_prefix}:{slot.name}")))


def slot_name_clashes(
    view: SchemaView,
) -> Iterator[tuple[SchemaDefinition, SlotDefinition, str, SlotDefinition]]:
    """Each application slot with the name of a toolkit slot and another IRI (#278).

    Yields the application module and slot, then the closure key of the toolkit module and its slot.
    LinkML has one namespace of slot names, so a merged view keeps only one of the two.
    """
    view.imports_closure()
    toolkit = {
        name: (key, slot)
        for key, schema in view.schema_map.items()
        if is_toolkit_module(schema)
        for name, slot in schema.slots.items()
    }
    for schema in list(view.schema_map.values()):
        if is_toolkit_module(schema):
            continue
        for name, slot in schema.slots.items():
            if name not in toolkit:
                continue
            key, theirs = toolkit[name]
            if slot_iri(view, schema, slot) != slot_iri(view, view.schema_map[key], theirs):
                yield schema, slot, key, theirs


def toolkit_carriers(view: SchemaView, name: str) -> list[str]:
    """The toolkit classes of the closure that carry the slot ``name``, sorted."""
    return sorted(
        cls.name
        for schema in view.schema_map.values()
        if is_toolkit_module(schema)
        for cls in schema.classes.values()
        if name in cls.slots or name in cls.slot_usage
    )


def prefer_application_slots(view: SchemaView) -> None:
    """Resolve a slot name to the application's slot when the toolkit's of that name is internal (#278).

    A toolkit slot that no toolkit class carries (the session's ``version``) leaves the view, so
    every reader (the mapper, the shapes, the context) finds the application's slot, whatever the
    import order. One that a toolkit class carries stays: the generator refuses that clash.
    The toolkit module is copied first; the loaded module may be shared.
    """
    shadowed: dict[str, set[str]] = {}
    for _, _, key, theirs in list(slot_name_clashes(view)):
        if not toolkit_carriers(view, str(theirs.name)):
            shadowed.setdefault(key, set()).add(str(theirs.name))
    for key, names in shadowed.items():
        module = deepcopy(view.schema_map[key])
        for name in names:
            del module.slots[name]
        view.schema_map[key] = module
    if shadowed:
        view.set_modified()
