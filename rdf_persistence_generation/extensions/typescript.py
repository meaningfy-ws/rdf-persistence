"""Step 6: TypeScript types, one file per schema module and an index (PD-25).

The stock ``gen-typescript`` renders one file from a template fixed in its source: enums become
``enum`` declarations (runtime code the JSON the API carries never needs), dates become ``Date`` objects
(JSON carries ISO strings), inlined parts are told apart from references by ``inlined`` flags this
toolkit does not set, ``internal`` slots are not skipped, and a slot narrowed in a subclass breaks
``extends``. This subclass keeps the stock name and identifier helpers and renders the toolkit's own
template: enums are unions of string literals, dates are strings, owned and inlined classes are
nested and every other class is an IRI string, ``linkml:Any`` is ``unknown``, and each interface
lists every slot of its class. A schema that renders here also gets ``rp_service.ts``, the toolkit's
service types; its module and type names are reserved.
"""

import json
import posixpath
from collections.abc import Mapping
from pathlib import Path

from linkml.generators.typescriptgen import TypescriptGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition, SlotDefinition

from rdf_persistence.schema.services.schema import (
    SERVED_SCHEMAS,
    load_schema,
    metamodel_importmap,
)
from rdf_persistence.schema.services.schema_structure import (
    apply_defaults,
    is_internal,
    is_owned,
    own_schemas,
    python_package_of,
)
from rdf_persistence_generation.config import toolkit_roots
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.generated.rp_generation import (
    GeneratedFile,
    TsEnum,
    TsEnumValue,
    TsField,
    TsImport,
    TsInterface,
    TsModule,
)
from rdf_persistence_generation.templating import environment

TEMPLATES = "typescript"
# The module that holds the types of every served schema (``rp_service.ts``). The name is the one
# consumers import: it is kept as it was when one schema held the service types, and it does not follow
# the schema of the ``api`` theme (``rp_api_entrypoints``), so the move changes no consumer's import (TC-07).
SERVICE_MODULE = "rp_service"
MODULE_TEMPLATE = "module.ts.jinja"
INDEX_TEMPLATE = "index.ts.jinja"
INDEX_NAME = "index.ts"
NUMBER_URIS = ("xsd:integer", "xsd:decimal", "xsd:double", "xsd:float")
BOOLEAN_URI = "xsd:boolean"
ANY_URI = "linkml:Any"


def _has_interface(cls: ClassDefinition) -> bool:
    """Mixins fold into their users and ``linkml:Any`` is ``unknown``; neither is an interface."""
    return not cls.mixin and cls.class_uri != ANY_URI


def doc(text: str | None) -> str:
    """A one-line doc comment of ``text``; empty when there is none."""
    if not text:
        return ""
    return f"/** {' '.join(text.split()).replace('*/', '*\\/')} */"


class ToolkitTypescriptGenerator(TypescriptGenerator):
    """``gen-typescript`` with the toolkit's templates; use ``module_files`` instead of ``serialize``."""

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
            cls = view.get_class(slot.range)
            if cls.class_uri == ANY_URI:
                return "unknown"
            return self.name(cls) if is_owned(slot) or view.is_inlined(slot) else "string"
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

    def modules(self) -> list[TsModule]:
        """The modules that define classes or enums, sorted by name."""
        self.schemaview.imports_closure()
        modules = [
            self.module(schema)
            for schema in self.schemaview.schema_map.values()
            if schema.enums or any(_has_interface(cls) for cls in schema.classes.values())
        ]
        return sorted(modules, key=lambda module: module.name)

    def module_files(self) -> list[GeneratedFile]:
        """One file per module that defines classes or enums."""
        return [_file(module) for module in self.modules()]


def _file(module: TsModule) -> GeneratedFile:
    text = environment(TEMPLATES).get_template(MODULE_TEMPLATE).render(module=module)
    return GeneratedFile(name=f"{module.name}.ts", text=text)


def with_index(files: list[GeneratedFile]) -> list[GeneratedFile]:
    """``files`` (module files) and the ``index.ts`` that exports each of them in sorted order."""
    names = sorted(file.name.removesuffix(".ts") for file in files)
    index = environment(TEMPLATES).get_template(INDEX_TEMPLATE).render(modules=names)
    return [*files, GeneratedFile(name=INDEX_NAME, text=index)]


def _generator(schema_path: Path) -> ToolkitTypescriptGenerator:
    generator = ToolkitTypescriptGenerator(str(schema_path), importmap=metamodel_importmap())
    apply_defaults(generator.schemaview, schema_path.parent, roots=toolkit_roots())
    return generator


def _module_files(schema_path: Path) -> list[GeneratedFile]:
    return _generator(schema_path).module_files()


def _clashes(generator: ToolkitTypescriptGenerator, folder: Path) -> list[str]:
    """The modules and types of the schemas kept in ``folder`` whose names the served types reserve."""
    served = [load_schema(path).schema for path in SERVED_SCHEMAS]
    reserved_modules = {SERVICE_MODULE, *(schema.name for schema in served)}
    reserved = {name for schema in served for name in (*schema.classes, *schema.enums)}
    found = []
    for schema in own_schemas(generator.schemaview, folder):
        if schema.name in reserved_modules:
            found.append(f"module {schema.name}")
        found += [
            f"{name} ({schema.name})"
            for name in (*schema.classes, *schema.enums)
            if name in reserved
        ]
    return found


def _is_served(schema_path: Path) -> bool:
    return schema_path.resolve() in {path.resolve() for path in SERVED_SCHEMAS}


def _specifier(owner: Path, module: str, folder: Path) -> str:
    """The path of ``module`` in ``owner``'s folder as ``folder``'s files import it (PD-4)."""
    spec = posixpath.relpath((owner / module).as_posix(), folder.as_posix())
    return spec if spec.startswith(".") else f"./{spec}"


def _imported_from_owners(
    generator: ToolkitTypescriptGenerator, owners: Mapping[str, Path], folder: Path
) -> dict[str, str]:
    """The specifier of each module another target writes as TypeScript, by module name (PD-3).

    A module is another target's when its ``python_package`` is a key of ``owners`` and is not the
    root schema's own.
    """
    own_package = python_package_of(generator.schemaview.schema)
    specifiers = {}
    for schema in generator.schemaview.schema_map.values():
        package = python_package_of(schema)
        if package is not None and package in owners and package != own_package:
            specifiers[schema.name] = _specifier(owners[package], schema.name, folder)
    return specifiers


def _importing(modules: list[TsModule], specifiers: Mapping[str, str]) -> list[TsModule]:
    """``modules`` without the imported ones, and the others' imports of them pointed at their owners."""
    kept = [module for module in modules if module.name not in specifiers]
    return [
        module.replaced(
            imports=sorted(
                (
                    TsImport(module=specifiers.get(item.module, item.module), names=item.names)
                    for item in module.imports
                ),
                key=lambda item: item.module,
            )
        )
        for module in kept
    ]


def render(
    schema_path: Path, *, folder: Path | None = None, owners: Mapping[str, Path] | None = None
) -> list[GeneratedFile]:
    """The TypeScript files of the schema at ``schema_path`` plus the types of every served schema.

    A consumer's API carries the service types (``rp_service`` and the other served schemas, PD-10),
    so they are written beside the modules the schema imports, in the order of ``SERVED_SCHEMAS``;
    the index exports every module once.

    A module whose ``python_package`` is a key of ``owners`` (the packages of the project's other
    targets that write TypeScript, to their folders) gets no file here: the modules that use it
    import it from the owner's folder, relative to ``folder``, this target's own.

    Raises:
        SchemaGenerationError: When the schema defines a module or type named like one of the served
            schemas, which both would be exported by ``index.ts``.
    """
    generator = _generator(schema_path)
    if not _is_served(schema_path) and (
        clashes := _clashes(generator, schema_path.resolve().parent)
    ):
        raise SchemaGenerationError(
            f"{', '.join(clashes)}: reserved by the served types ({SERVICE_MODULE}.ts and its kin); rename"
        )
    modules = generator.modules()
    if folder is not None and owners:  # no folder or no owner: every module is copied
        modules = _importing(modules, _imported_from_owners(generator, owners, folder))
    return with_index(_with_served(modules))


def _with_served(modules: list[TsModule]) -> list[GeneratedFile]:
    """``modules`` and the served schemas' modules; the served schemas' own types share one file.

    The file is named ``SERVICE_MODULE`` (``rp_service``) whichever schema is served first, and holds
    the types of every served schema in ``SERVED_SCHEMAS`` order, so splitting the service schema
    changes neither its name nor the order of its types (TC-07).
    """
    served_names = [load_schema(path).schema.name for path in SERVED_SCHEMAS]
    by_name = {m.name: m for m in modules if m.name not in served_names}
    own: list[TsModule] = []
    for served, name in zip(SERVED_SCHEMAS, served_names, strict=True):
        for module in _generator(served).modules():
            if module.name == name:
                own.append(module)
            elif module.name not in served_names:
                by_name.setdefault(module.name, module)
    if own:
        by_name[SERVICE_MODULE] = _merged(own, served_names)
    return [_file(_pointing_at_merged(by_name[name], served_names)) for name in sorted(by_name)]


def _pointing_at_merged(module: TsModule, served_names: list[str]) -> TsModule:
    """``module`` with each import of a served schema's module pointed at ``SERVICE_MODULE``.

    A served schema has no file of its own (its types are in the merged one), so an import of
    ``./<served schema>`` would name a file that is not written (D-10).
    """
    if not any(item.module in served_names for item in module.imports):
        return module
    imports: dict[str, set[str]] = {}
    for item in module.imports:
        source = SERVICE_MODULE if item.module in served_names else item.module
        imports.setdefault(source, set()).update(item.names)
    return module.replaced(
        imports=[
            TsImport(module=source, names=sorted(names))
            for source, names in sorted(imports.items())
        ]
    )


def _merged(modules: list[TsModule], served_names: list[str]) -> TsModule:
    """One module named ``SERVICE_MODULE``, with the enums and interfaces of all in order."""
    imports: dict[str, set[str]] = {}
    for module in modules:
        for item in module.imports:
            imports.setdefault(item.module, set()).update(item.names)
    return TsModule(
        name=SERVICE_MODULE,
        enums=[e for module in modules for e in module.enums],
        interfaces=[i for module in modules for i in module.interfaces],
        imports=[
            TsImport(module=source, names=sorted(names))
            for source, names in sorted(imports.items())
            if source not in served_names
        ],
    )
