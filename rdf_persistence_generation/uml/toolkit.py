"""The toolkit index (PD-17, PD-18, PD-20; F-1, F-3, F-11): what the toolkit's metamodel offers a converted model.

The metamodel (``rp.yaml``) is read once, with ``linkml_runtime`` only (the contract
``works-without-the-generate-extra``). Classes are found by name and by expanded ``class_uri``, slots by
expanded ``slot_uri``; the class annotations and the toolkit-filled slots are read from the metamodel, never
listed here (A-1). Results are ``linkml_runtime`` definitions.
"""

import functools
from collections.abc import Mapping
from typing import Final

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.schema.services.schema import PACKAGE_DIR, load_schema
from rdf_persistence_generation.checks.toolkit_filled import toolkit_filled_slots
from rdf_persistence_generation.config import METAMODEL_ROOT

IMPORT_FORM: Final = "rdf_persistence/model/"  # F-11: how an application imports a toolkit module
CLASS_ANNOTATION_MARK: Final = "Class annotation"  # F-1: how the metamodel describes them


class Toolkit:
    """The classes, slots and class annotations of the toolkit's metamodel, indexed for lookup."""

    def __init__(self, view: SchemaView) -> None:
        self._view = view
        classes = view.all_classes()
        self._classes: dict[str, ClassDefinition] = dict(classes)
        self._class_uris = {self.class_uri(name): each for name, each in classes.items()}
        self._filled = toolkit_filled_slots(view)
        self._slot_uris: dict[str, SlotDefinition] = {}
        for slot in view.all_slots(attributes=False).values():
            if not slot.identifier:
                self._slot_uris.setdefault(str(view.get_uri(slot, expand=True)), slot)
        values = view.get_enum(RpAnnotation.__name__).permissible_values
        self.class_annotations: tuple[str, ...] = tuple(
            name
            for name, value in values.items()
            if str(value.description or "").startswith(CLASS_ANNOTATION_MARK)
        )

    def class_by_name(self, name: str) -> ClassDefinition | None:
        return self._classes.get(name)

    def toolkit_class(self, name: str) -> ClassDefinition:
        """The toolkit class ``name``; a ``KeyError`` when there is none (a caller bug: it checked first)."""
        return self._classes[name]

    def toolkit_slot(self, iri: str) -> SlotDefinition:
        """The reusable toolkit slot whose expanded ``slot_uri`` is ``iri``; a ``KeyError`` when there is none."""
        return self._slot_uris[iri]

    def prefixes(self) -> Mapping[str, str]:
        """The prefix name and namespace of every prefix the metamodel declares (PD-6)."""
        return {prefix: str(namespace) for prefix, namespace in self._view.namespaces().items()}

    def class_names(self) -> list[str]:
        """The names of every toolkit class, sorted."""
        return sorted(self._classes)

    def class_by_uri(self, uri: str) -> ClassDefinition | None:
        """The toolkit class whose expanded ``class_uri`` is ``uri``."""
        return self._class_uris.get(uri)

    def class_uri(self, name: str) -> str:
        """The expanded ``class_uri`` of the toolkit class ``name``."""
        return str(self._view.get_uri(self._classes[name], expand=True))

    def module_of(self, name: str) -> str:
        """The import of the module that defines the toolkit class ``name`` (F-11)."""
        source = self._classes[name].from_schema
        module = next(
            str(schema.name) for schema in self._view.all_schema() if str(schema.id) == source
        )
        return IMPORT_FORM + module

    def slot_by_uri(self, uri: str) -> SlotDefinition | None:
        """The reusable toolkit slot whose expanded ``slot_uri`` is ``uri``; never the identifier."""
        return self._slot_uris.get(uri)

    def module_of_slot(self, slot_name: str) -> str:
        """The import of the module that defines the toolkit slot ``slot_name`` (F-11)."""
        return IMPORT_FORM + str(self._view.in_schema(slot_name))

    def inherits(self, class_names: list[str], slot_name: str) -> bool:
        """True when a toolkit class of ``class_names`` has the slot, itself or through its parents and mixins."""
        return any(slot_name in self._view.class_slots(name) for name in class_names)

    def required_on(self, class_names: list[str], slot_name: str) -> bool:
        """Whether the slot is required where a class of ``class_names`` has it; else as the toolkit defines it."""
        having = [name for name in class_names if slot_name in self._view.class_slots(name)]
        if not having:
            return bool(self._view.get_slot(slot_name).required)
        return any(self._view.induced_slot(slot_name, name).required for name in having)

    def is_filled(self, slot_name: str) -> bool:
        """True when the toolkit fills the slot itself (``toolkit_filled: true``)."""
        return slot_name in self._filled


@functools.cache
def load_toolkit() -> Toolkit:
    """The index of the installed toolkit's metamodel, read once."""
    return Toolkit(load_schema(PACKAGE_DIR / "model" / METAMODEL_ROOT))
