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
from rdf_persistence.services.schema import PACKAGE_DIR, metamodel_importmap
from rdf_persistence.services.schema_structure import apply_defaults, is_internal, is_owned

TEMPLATES = "typescript"
MODULE_TEMPLATE = "module.ts.jinja"
INDEX_TEMPLATE = "index.ts.jinja"
INDEX_NAME = "index.ts"
NUMBER_URIS = ("xsd:integer", "xsd:decimal", "xsd:double", "xsd:float")
BOOLEAN_URI = "xsd:boolean"
ANY_URI = "linkml:Any"
SERVICE_SCHEMA = PACKAGE_DIR / "model" / "service" / "rp_service.yaml"


def _has_interface(cls: ClassDefinition) -> bool:
    """Mixins fold into their users and ``linkml:Any`` is ``unknown``; neither is an interface."""
    return not cls.mixin and cls.class_uri != ANY_URI


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
            if view.get_class(slot.range).class_uri == ANY_URI:
                return "unknown"
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
        classes = [cls for cls in schema.classes.values() if _has_interface(cls)]
        interfaces = [self._interface(self.schemaview.get_class(cls.name)) for cls in classes]
        return TsModule(
            name=schema.name,
            enums=[self._enum(name) for name in schema.enums],
            interfaces=interfaces,
            imports=self._imports(schema.name, interfaces),
        )

    def files(self) -> list[GeneratedFile]:
        """One file per module that defines classes or enums, and ``index.ts`` exporting them."""
        return index_added(self.module_files())

    def module_files(self) -> list[GeneratedFile]:
        """One file per module that defines classes or enums."""
        env = environment(TEMPLATES)
        self.schemaview.imports_closure()
        modules = [
            self.module(schema)
            for schema in self.schemaview.schema_map.values()
            if schema.enums or any(_has_interface(cls) for cls in schema.classes.values())
        ]
        modules.sort(key=lambda module: module.name)
        return [
            GeneratedFile(
                name=f"{module.name}.ts",
                text=env.get_template(MODULE_TEMPLATE).render(module=module),
            )
            for module in modules
        ]


def index_added(files: list[GeneratedFile]) -> list[GeneratedFile]:
    """``files`` (module files, in order) and the ``index.ts`` that exports each of them."""
    names = sorted(file.name.removesuffix(".ts") for file in files)
    index = environment(TEMPLATES).get_template(INDEX_TEMPLATE).render(modules=names)
    return [*files, GeneratedFile(name=INDEX_NAME, text=index)]


def _module_files(schema_path: Path) -> list[GeneratedFile]:
    generator = ToolkitTypescriptGenerator(str(schema_path), importmap=metamodel_importmap())
    apply_defaults(generator.schemaview, schema_path.parent)
    return generator.module_files()


def render(schema_path: Path) -> list[GeneratedFile]:
    """The TypeScript files of the schema at ``schema_path`` plus the toolkit's service types.

    A consumer's API carries the service types (``rp_service``), so they are written beside the
    modules the schema imports; the index exports every module once.
    """
    files = _module_files(schema_path)
    if schema_path.resolve() != SERVICE_SCHEMA.resolve():
        written = {file.name for file in files}
        files += [f for f in _module_files(SERVICE_SCHEMA) if f.name not in written]
    return index_added(files)
