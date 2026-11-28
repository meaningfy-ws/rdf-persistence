"""The checks a consumer's run makes against the toolkit's technical modules (PD-2, PD-2a).

A consumer class may build on a toolkit class only when ``rdf_persistence`` exports it, and may not
declare a slot whose field shadows one of the toolkit class it extends. The toolkit's own run is not
checked.
"""

import keyword
from pathlib import Path

from linkml.generators.pydanticgen.pydanticgen import make_valid_python_identifier
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.schema.services.schema_structure import (
    FIELD_NAME_SLOT,
    annotation_text,
    is_toolkit_schema,
    own_schemas,
)
from rdf_persistence.schema.services.vocabulary import METAMODEL
from rdf_persistence_generation.config import toolkit_roots
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.generated.rp_generation import GenerationAnnotation

METAMODEL_DIR = METAMODEL.parent


def is_toolkit_technical(path: Path) -> bool:
    """Whether the schema file is one of the toolkit's technical modules (``model/technical/``)."""
    return (METAMODEL_DIR / "technical").resolve() in path.resolve().parents


def is_python_name(alias: str | None) -> bool:
    """Whether the stock field name, which is the slot's alias when it has one, can stand as it is.

    The stock generator names a field after the alias and sets ``alias=`` only when the two differ;
    a dotted alias (``rp.step``) would become ``rp_step``. Such a slot is named after itself instead.
    """
    return alias is None or (alias.isidentifier() and not keyword.iskeyword(alias))


def _field_name(slot: SlotDefinition) -> str:
    """The Python field a slot becomes: its alias when that is a Python name, else the slot's own name."""
    opted_in = annotation_text(slot, GenerationAnnotation.FIELD_NAME) == FIELD_NAME_SLOT
    if slot.alias and is_python_name(slot.alias) and not opted_in:
        return str(slot.alias)
    return str(make_valid_python_identifier(underscore(slot.name)))


def _exported_names() -> frozenset[str]:
    """The names ``rdf_persistence`` exports."""
    import rdf_persistence  # here: the generated code may not exist yet on a toolkit run

    return frozenset(rdf_persistence.__all__)


def _technical_classes(view: SchemaView) -> dict[str, str]:
    """The classes of the toolkit's technical modules in the closure of ``view``, each with its module's name."""
    return {
        name: schema.name
        for schema in view.schema_map.values()
        if is_toolkit_technical(Path(str(schema.source_file)))
        for name in schema.classes
    }


def _technical_enums(view: SchemaView) -> dict[str, str]:
    """The enums of the toolkit's technical modules in the closure of ``view``, each with its module's name."""
    return {
        name: schema.name
        for schema in view.schema_map.values()
        if is_toolkit_technical(Path(str(schema.source_file)))
        for name in schema.enums
    }


def unexported_technical(view: SchemaView) -> set[str]:
    """The Python names of the classes and enums of the toolkit's technical modules that the package does not export."""
    names = {camelcase(name) for name in (*_technical_classes(view), *_technical_enums(view))}
    return names - _exported_names()


def _named_by(cls: ClassDefinition, view: SchemaView) -> list[str]:
    """The classes ``cls`` names itself: its ``is_a``, its mixins and the ranges of the slots it declares."""
    named = [cls.is_a, *cls.mixins]
    named += [view.induced_slot(name, cls.name).range for name in (*cls.slots, *cls.attributes)]
    named += [usage.range for usage in cls.slot_usage.values()]
    return [str(name) for name in named if name]


def refuse_unsupported_extensions(view: SchemaView, folder: Path) -> None:
    """Refuse a consumer class that builds on a toolkit technical class, or ranges a slot to a toolkit
    technical enum, that the package does not export (PD-2, PD-8),
    or whose own slot shadows a field of the toolkit class it extends (PD-2a).

    Raises:
        SchemaGenerationError: Naming the consumer class and the toolkit class or field.
    The toolkit's own run is not checked.
    """
    if is_toolkit_schema(folder, roots=toolkit_roots()):
        return
    exported = _exported_names()
    technical = _technical_classes(view)
    named = {**technical, **_technical_enums(view)}
    for schema in own_schemas(view, folder):
        for cls in schema.classes.values():
            for name in _named_by(cls, view):
                if name in named and camelcase(name) not in exported:
                    raise SchemaGenerationError(
                        f"{cls.name} uses {name} of {named[name]}, "
                        "which rdf_persistence does not export"
                    )
            _refuse_shadowing(cls, view, technical)


def _refuse_shadowing(cls: ClassDefinition, view: SchemaView, technical: dict[str, str]) -> None:
    """Refuse an own slot of ``cls`` whose field is a field of a toolkit ancestor's other slot (PD-2a)."""
    own = [view.induced_slot(name, cls.name) for name in (*cls.slots, *cls.attributes)]
    for ancestor in view.class_ancestors(cls.name, reflexive=False):
        if ancestor not in technical:
            continue
        fields = {_field_name(slot): slot.name for slot in view.class_induced_slots(ancestor)}
        for slot in own:
            field_name = _field_name(slot)
            if fields.get(field_name, slot.name) != slot.name:
                raise SchemaGenerationError(
                    f"{cls.name}.{slot.name} shadows {ancestor}.{field_name}"
                )
