"""The conversion (PD-5, PD-14 as D-5 amends it, PD-22 order): a ``UmlModel`` to LinkML schemas.

``convert`` is pure: no file is read or written. Passes, in order: classify the classes (``classes``),
read the slots (``slots``, ``links``), lay the packages out as modules and merge the ones that import
each other (``modules``), then write each module as a ``SchemaDefinition``. When any problem was found
the schemas are not built: the caller prints the problems and writes nothing.
"""

from collections.abc import Mapping
from typing import Final

from linkml_runtime.linkml_model import (
    ClassDefinition,
    EnumDefinition,
    Prefix,
    SchemaDefinition,
)

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    ReportKind,
    ReportLine,
    UmlModel,
    UmlRule,
    UmlSettings,
)
from rdf_persistence_generation.uml.classes import (
    RP_CORE_IMPORT,
    annotation,
    build_class,
    build_enum,
    collect_elements,
    parents,
)
from rdf_persistence_generation.uml.context import Context, Element
from rdf_persistence_generation.uml.links import link_usages, owned_pairs
from rdf_persistence_generation.uml.modules import (
    PATH_SEPARATOR,
    ModulePath,
    cycle_components,
    module_name,
    package_paths,
)
from rdf_persistence_generation.uml.naming import title_for
from rdf_persistence_generation.uml.slots import SharedSlots, Usage, attribute_usages, share

LINKML_TYPES: Final = "linkml:types"
LINKML_PREFIX: Final = ("linkml", "https://w3id.org/linkml/")
ANNOTATIONS_IMPORT: Final = "rdf_persistence/model/rp_annotations"
MODULE_KIND: Final = "module_kind"
DOMAIN: Final = "domain"
DEFAULT_RANGE: Final = "string"


class Layout:
    """The generated elements, the packages' references and the module each package is written in (D-5)."""

    def __init__(
        self,
        elements: list[Element],
        edges: Mapping[ModulePath, set[ModulePath]],
        merged: Mapping[ModulePath, ModulePath],
        names: Mapping[ModulePath, str],
    ) -> None:
        self.elements = elements
        self.edges = edges
        self.merged = merged
        self.names = names

    def members(self, path: ModulePath) -> list[Element]:
        return [each for each in self.elements if self.merged[each.path] == path]

    def refers_to(self, path: ModulePath) -> set[str]:
        """The modules the module at ``path`` imports."""
        return {
            self.names[self.merged[target]]
            for source in self.edges
            if self.merged[source] == path
            for target in self.edges[source]
        }


def _generated(ctx: Context) -> list[Element]:
    """The elements that become a definition; an enumeration with no literal does not."""
    return [
        element
        for element in sorted(ctx.elements.values(), key=lambda each: (each.path, each.label))
        if not (element.is_enum and not element.literals)
    ]


def _usages(ctx: Context, model: UmlModel, elements: list[Element]) -> list[Usage]:
    usages = [
        usage
        for element in elements
        if not element.is_enum
        for usage in attribute_usages(ctx, element)
    ]
    usages.extend(link_usages(ctx, model, owned_pairs(ctx, model)))
    return usages


def _references(
    elements: list[Element], usages: list[Usage], parent_of: Mapping[int, str]
) -> dict[ModulePath, set[ModulePath]]:
    """For each package path, the package paths its classes refer to (``is_a``, slot ranges)."""
    by_label = {element.label: element for element in elements}
    edges: dict[ModulePath, set[ModulePath]] = {element.path: set() for element in elements}
    for child_id, parent in parent_of.items():
        child = next(each for each in elements if each.uml.object_id == child_id)
        edges[child.path].add(by_label[parent].path)
    for usage in usages:
        target = by_label.get(usage.shape.range)
        if target is not None:
            edges[usage.holder.path].add(target.path)
    for path, targets in edges.items():
        targets.discard(path)
    return edges


def _layout(
    ctx: Context, elements: list[Element], edges: Mapping[ModulePath, set[ModulePath]]
) -> dict[ModulePath, ModulePath]:
    """The path each package is written under: its own, or the first of the cycle it is in (D-5)."""
    merged = {path: path for path in edges}
    root_name = ctx.settings.root_name
    for component in cycle_components(list(edges), dict(edges)):
        for path in component:
            merged[path] = component[0]
        names = ", ".join("/".join(path) or "main" for path in component)
        ctx.findings.note(
            ReportKind.MERGED_CYCLE,
            module_name(root_name, component[0]),
            f"the packages {names} are written as one module",
        )
    return merged


def _module_names(ctx: Context, paths: set[ModulePath]) -> dict[ModulePath, str]:
    """The module name of each path; two paths with one name are a problem naming both (PD-5)."""
    names: dict[ModulePath, str] = {}
    owner: dict[str, ModulePath] = {}
    for path in sorted(paths):
        name = module_name(ctx.settings.root_name, path)
        names[path] = name
        first = owner.setdefault(name, path)
        if first != path:
            ctx.findings.problem(
                UmlRule.PACKAGE_MODULE,
                name,
                f"the packages {'/'.join(first) or 'main'} and {'/'.join(path)} both give the module {name}",
            )
    return names


def _prefixes_of(ctx: Context, schema: SchemaDefinition) -> None:
    """Declare the prefixes the definitions use, besides ``linkml`` and the default one."""
    wanted: dict[str, str] = dict([LINKML_PREFIX])
    wanted[ctx.settings.default_prefix] = ctx.default_namespace()
    curies = [definition.class_uri for definition in schema.classes.values()]
    curies += [definition.slot_uri for definition in schema.slots.values()]
    curies += [
        value.meaning
        for enum in schema.enums.values()
        for value in enum.permissible_values.values()
    ]
    for curie in curies:
        used = ctx.used_prefix(curie)
        if used is not None and used[1]:
            wanted[used[0]] = used[1]
    for name in sorted(wanted):
        schema.prefixes[name] = Prefix(prefix_prefix=name, prefix_reference=wanted[name])
    schema.default_prefix = ctx.settings.default_prefix
    schema.default_range = DEFAULT_RANGE


class Built:
    """What the passes made, before the modules are written."""

    def __init__(
        self,
        definitions: tuple[dict[int, ClassDefinition], dict[int, EnumDefinition]],
        shared: SharedSlots,
        slot_names: dict[int, list[str]],
    ) -> None:
        self.classes, self.enums = definitions
        self.shared = shared
        self.slot_names = slot_names


def _build(ctx: Context, model: UmlModel) -> tuple[list[Element], list[Usage], dict[int, str]]:
    collect_elements(ctx, model)
    elements = _generated(ctx)
    return elements, _usages(ctx, model, elements), parents(ctx, model)


def _enums(ctx: Context) -> dict[int, EnumDefinition]:
    """The enum of each enumeration; an empty one makes none but a report line (D-10)."""
    enums: dict[int, EnumDefinition] = {}
    for element in sorted(ctx.elements.values(), key=lambda each: (each.path, each.label)):
        built = build_enum(ctx, element) if element.is_enum else None
        if built is not None:
            enums[element.uml.object_id] = built
    return enums


def _slot_names(usages: list[Usage], ctx: Context) -> dict[int, list[str]]:
    names: dict[int, list[str]] = {}
    for usage in sorted(usages, key=lambda each: each.order):
        held = names.setdefault(usage.holder.uml.object_id, [])
        if usage.name not in held:
            held.append(usage.name)
    return names


def _write_module(
    ctx: Context, name: str, path: ModulePath, built: Built, members: list[Element]
) -> SchemaDefinition:
    settings = ctx.settings
    first = path[-1] if path else settings.subtree_package.rsplit(PATH_SEPARATOR, 1)[-1]
    note = next((ctx.paths[i].note for i in ctx.paths if ctx.paths[i].below == path), None)
    schema = SchemaDefinition(
        id=settings.schema_base + name,
        name=name,
        title=title_for(first),
        description=(note or "").replace("\r\n", "\n").strip()
        or f"The {first} package of the {settings.root_name} model, converted from UML.",
        annotations={MODULE_KIND: annotation(MODULE_KIND, DOMAIN)},
    )
    for element in members:
        _place(schema, element, built)
    for slot_name, slot in sorted(built.shared.definitions.items()):
        if built.shared.home[slot_name] == name:
            schema.slots[slot_name] = slot
    return schema


def _place(schema: SchemaDefinition, element: Element, built: Built) -> None:
    key = element.uml.object_id
    if element.is_enum:
        schema.enums[element.label] = built.enums[key]
        return
    definition = built.classes[key]
    definition.slots = built.slot_names.get(key, [])
    definition.slot_usage = built.shared.class_usage.get(element.label, {})
    schema.classes[element.label] = definition


def _imports(name: str, members: list[Element], refs: set[str]) -> list[str]:
    toolkit = [ANNOTATIONS_IMPORT]
    if any(element.is_root for element in members):
        toolkit.append(RP_CORE_IMPORT)
    return [LINKML_TYPES, *sorted(toolkit), *sorted(refs - {name})]


def convert(
    model: UmlModel, settings: UmlSettings, metamodel_prefixes: Mapping[str, str]
) -> tuple[list[SchemaDefinition], list[ReportLine], list[CheckProblem]]:
    """Convert the subtree of ``model`` into a root schema and one module per package (or merged cycle).

    Returns the schemas (root first, then the modules by path), the report lines and the problems, each
    sorted. With any problem the schemas are empty: nothing is to be written.
    """
    prefixes = {each.prefix_name: each.namespace for each in settings.prefixes or []}
    ctx = Context(settings, metamodel_prefixes, prefixes)
    ctx.paths = package_paths(model, settings)
    elements, usages, parent_of = _build(ctx, model)
    if not ctx.elements and not ctx.findings.problems():
        ctx.findings.problem(
            UmlRule.PACKAGE_MODULE,
            settings.subtree_package,
            "the package holds no class or enumeration to convert",
        )
    edges = _references(elements, usages, parent_of)
    merged = _layout(ctx, elements, edges)
    names = _module_names(ctx, set(merged.values()))
    module_of = {element.uml.object_id: names[merged[element.path]] for element in elements}
    shared = share(ctx, usages, module_of)
    classes = {
        e.uml.object_id: build_class(ctx, e, parent_of.get(e.uml.object_id))
        for e in elements
        if not e.is_enum
    }
    built = Built((classes, _enums(ctx)), shared, _slot_names(usages, ctx))
    problems = ctx.findings.problems()
    if problems:
        return [], ctx.findings.report(), problems
    schemas = _assemble(ctx, Layout(elements, edges, merged, names), built)
    return schemas, ctx.findings.report(), []


def _assemble(ctx: Context, layout: Layout, built: Built) -> list[SchemaDefinition]:
    """The root schema first, then each module by path, with its imports."""
    modules: list[SchemaDefinition] = []
    for path in sorted(layout.names):
        name = layout.names[path]
        members = layout.members(path)
        schema = _write_module(ctx, name, path, built, members)
        schema.imports = _imports(name, members, layout.refers_to(path))
        _prefixes_of(ctx, schema)
        modules.append(schema)
    return [_root(ctx, [m.name for m in modules]), *modules]


def _root(ctx: Context, module_names: list[str]) -> SchemaDefinition:
    settings = ctx.settings
    root = SchemaDefinition(
        id=settings.schema_base + settings.root_name,
        name=settings.root_name,
        title=title_for(settings.root_name),
        description=f"The {settings.root_name} model, converted from UML.",
        version=settings.schema_version,
        imports=[LINKML_TYPES, *module_names],
    )
    _prefixes_of(ctx, root)
    return root
