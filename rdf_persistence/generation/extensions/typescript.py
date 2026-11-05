"""Step 6: TypeScript types, one file per schema module and an index (PD-25).

The stock ``gen-typescript`` renders one file from a template fixed in its source: enums become
``enum`` declarations (runtime code the JSON the API carries never needs), dates become ``Date`` objects
(JSON carries ISO strings), inlined parts are told apart from references by ``inlined`` flags this
toolkit does not set, ``internal`` slots are not skipped, and a slot narrowed in a subclass breaks
``extends``. This subclass keeps the stock name and identifier helpers and renders the toolkit's own
template: enums are unions of string literals, dates are strings, owned parts are nested and every
other class is an IRI string, and each interface lists every slot of its class.
"""

import json
from pathlib import Path

from linkml.generators.typescriptgen import TypescriptGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition, SlotDefinition

from rdf_persistence.generation.generated.rp_generation import (
    GeneratedFile,
    TsEnum,
    TsEnumValue,
    TsField,
    TsImport,
    TsInterface,
    TsModule,
)
from rdf_persistence.generation.templating import environment
from rdf_persistence.services.schema import metamodel_importmap
from rdf_persistence.services.schema_structure import apply_defaults, is_internal, is_owned

TEMPLATES = "typescript"
MODULE_TEMPLATE = "module.ts.jinja"
INDEX_TEMPLATE = "index.ts.jinja"
INDEX_NAME = "index.ts"
NUMBER_URIS = ("xsd:integer", "xsd:decimal", "xsd:double", "xsd:float")
BOOLEAN_URI = "xsd:boolean"


def doc(text: str | None) -> str:
    """A one-line doc comment of ``text``; empty when there is none."""
    if not text:
        return ""
    return f"/** {' '.join(text.split()).replace('*/', '*\\/')} */"


class ToolkitTypescriptGenerator(TypescriptGenerator):
    """``gen-typescript`` with the toolkit's templates; use ``files`` instead of ``serialize``."""

    def module_of_type(self) -> dict[str, str]:
        """The schema module that defines each class and enum, by TypeScript name."""
        return {
            self.name(element): schema.name
            for schema in self.schemaview.schema_map.values()
            for element in (*schema.classes.values(), *schema.enums.values())
        }

    def range(self, slot: SlotDefinition) -> str:
        """The TypeScript type of the slot's values (without ``[]``)."""
        view = self.schemaview
        if slot.range in view.all_classes():
            return self.name(view.get_class(slot.range)) if is_owned(slot) else "string"
        if slot.range in view.all_enums():
            return str(self.name(view.get_enum(slot.range)))
        return self._scalar(slot.range)

    def _scalar(self, type_name: str | None) -> str:
        view = self.schemaview
        for ancestor in view.type_ancestors(type_name) if type_name in view.all_types() else []:
            uri = view.get_type(ancestor).uri
            if uri in NUMBER_URIS:
                return "number"
            if uri == BOOLEAN_URI:
                return "boolean"
            if uri:
                return "string"
        return "string"

    def _field(self, slot: SlotDefinition) -> TsField:
        suffix = "[]" if slot.multivalued else ""
        optional = not (slot.required or slot.identifier)
        return TsField(
            name=self.name(slot),
            type=f"{self.range(slot)}{suffix}",
            optional=optional,
            doc=doc(slot.description),
        )

    def _interface(self, cls: ClassDefinition) -> TsInterface:
        slots = [
            slot for slot in self.schemaview.class_induced_slots(cls.name) if not is_internal(slot)
        ]
        return TsInterface(
            name=self.name(cls), doc=doc(cls.description), fields=[self._field(s) for s in slots]
        )

    def _enum(self, name: str) -> TsEnum:
        enum = self.schemaview.get_enum(name)
        values = [
            TsEnumValue(literal=json.dumps(text), doc=doc(value.description))
            for text, value in enum.permissible_values.items()
        ]
        return TsEnum(name=self.name(enum), doc=doc(enum.description), values=values)

    def _imports(self, module: str, interfaces: list[TsInterface]) -> list[TsImport]:
        """The classes and enums the module's fields name that another module defines."""
        defined_in = self.module_of_type()
        wanted: dict[str, set[str]] = {}
        for interface in interfaces:
            for item in interface.fields:
                name = item.type.removesuffix("[]")
                source = defined_in.get(name)
                if source and source != module:
                    wanted.setdefault(source, set()).add(name)
        return [
            TsImport(module=source, names=sorted(names)) for source, names in sorted(wanted.items())
        ]

    def module(self, schema: SchemaDefinition) -> TsModule:
        classes = [cls for cls in schema.classes.values() if not cls.mixin]
        interfaces = [self._interface(self.schemaview.get_class(cls.name)) for cls in classes]
        return TsModule(
            name=schema.name,
            enums=[self._enum(name) for name in schema.enums],
            interfaces=interfaces,
            imports=self._imports(schema.name, interfaces),
        )

    def files(self) -> list[GeneratedFile]:
        """One file per module that defines classes or enums, and ``index.ts`` exporting them."""
        env = environment(TEMPLATES)
        self.schemaview.imports_closure()
        modules = [
            self.module(schema)
            for schema in self.schemaview.schema_map.values()
            if schema.enums or any(not cls.mixin for cls in schema.classes.values())
        ]
        modules.sort(key=lambda module: module.name)
        files = [
            GeneratedFile(
                name=f"{module.name}.ts",
                text=env.get_template(MODULE_TEMPLATE).render(module=module),
            )
            for module in modules
        ]
        index = env.get_template(INDEX_TEMPLATE).render(modules=[module.name for module in modules])
        return [*files, GeneratedFile(name=INDEX_NAME, text=index)]


def render(schema_path: Path) -> list[GeneratedFile]:
    """The TypeScript files of the schema at ``schema_path``."""
    generator = ToolkitTypescriptGenerator(str(schema_path), importmap=metamodel_importmap())
    apply_defaults(generator.schemaview, schema_path.parent)
    return generator.files()
