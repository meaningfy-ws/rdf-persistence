"""The conversion (PD-5, PD-14 as D-5 amends it, PD-22 order): a ``UmlModel`` to LinkML schemas.

``convert`` is pure: no file is read or written. Passes, in order: classify the classes (``classes``),
read the slots (``slots``, ``links``), lay the packages out as modules, one each, that may import each
other (``modules``), then write each module as a ``SchemaDefinition``. When any problem was found
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

from rdf_persistence.core.domain.generated.rp_core import ModuleKind, RpAnnotation
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    ReportLine,
    UmlElement,
    UmlModel,
    UmlRule,
    UmlSettings,
)
from rdf_persistence_generation.uml.classes import (
    annotation,
    build_class,
    build_enum,
    collect_elements,
    mark_abstract_roots,
    parents,
)
from rdf_persistence_generation.uml.context import (
    Context,
    below_of,
    is_boundary_root,
    literals_of,
    path_of,
)
from rdf_persistence_generation.uml.links import link_usages, owned_pairs
from rdf_persistence_generation.uml.mixins import check_default_mixins
from rdf_persistence_generation.uml.modules import (
    PATH_SEPARATOR,
    ModulePath,
    module_name,
    package_paths,
    reachable,
)
from rdf_persistence_generation.uml.naming import title_for
from rdf_persistence_generation.uml.roles import ROLES_SUFFIX, role_entries, roles_file_text
from rdf_persistence_generation.uml.slots import (
    SharedSlots,
    Usage,
    attribute_usages,
    choose_homes,
    is_owned,
    name_slots,
    share,
    shared_edges,
    split_toolkit,
    use_toolkit_slots,
)
from rdf_persistence_generation.uml.tags import package_kind
from rdf_persistence_generation.uml.toolkit import Toolkit
from rdf_persistence_generation.uml.workflows import workflow_entries, workflow_files

LINKML_TYPES: Final = "linkml:types"
LINKML_PREFIX: Final = ("linkml", "https://w3id.org/linkml/")
ANNOTATIONS_IMPORT: Final = "rdf_persistence/model/rp_annotations"
MODULE_KIND: Final = RpAnnotation.MODULE_KIND.value
DOMAIN: Final = ModuleKind.DOMAIN.value
DEFAULT_RANGE: Final = "string"


class Layout:
    """The generated elements, the packages' references and the module of each package (PD-8)."""

    def __init__(
        self,
        elements: list[UmlElement],
        edges: Mapping[ModulePath, set[ModulePath]],
        names: Mapping[ModulePath, str],
    ) -> None:
        self.elements = elements
        self.edges = edges
        self.names = names

    def members(self, path: ModulePath) -> list[UmlElement]:
        return [each for each in self.elements if path_of(each) == path]

    def refers_to(self, path: ModulePath) -> set[str]:
        """The modules the module at ``path`` imports."""
        return {self.names[target] for target in self.edges.get(path, ())}


def _generated(ctx: Context) -> list[UmlElement]:
    """The elements that become a definition; an enumeration with no literal does not."""
    return [
        element
        for element in sorted(ctx.elements.values(), key=lambda each: (path_of(each), each.label))
        if not (element.is_enum and not literals_of(element))
    ]


def _usages(ctx: Context, model: UmlModel, elements: list[UmlElement]) -> list[Usage]:
    usages = [
        usage
        for element in elements
        if not element.is_enum
        for usage in attribute_usages(ctx, element)
    ]
    usages.extend(link_usages(ctx, model, owned_pairs(ctx, model)))
    return usages


def _references(
    elements: list[UmlElement], usages: list[Usage], parent_of: Mapping[int, str]
) -> dict[ModulePath, set[ModulePath]]:
    """For each package path, the package paths its classes refer to (``is_a``, slot ranges)."""
    by_label = {element.label: element for element in elements}
    edges: dict[ModulePath, set[ModulePath]] = {path_of(element): set() for element in elements}
    for child_id, parent in parent_of.items():
        child = next(each for each in elements if each.uml_class.object_id == child_id)
        edges[path_of(child)].add(path_of(by_label[parent]))
    for usage in usages:
        target = by_label.get(usage.shape.range)
        if target is not None:
            edges[path_of(usage.holder)].add(path_of(target))
    for path, targets in edges.items():
        targets.discard(path)
    return edges


Edges = dict[ModulePath, set[ModulePath]]


def _grown(
    edges: Mapping[ModulePath, set[ModulePath]], added: Mapping[ModulePath, set[ModulePath]]
) -> Edges:
    grown: Edges = {path: set(targets) for path, targets in edges.items()}
    for path, targets in added.items():
        grown.setdefault(path, set()).update(targets)
        grown[path].discard(path)
    return grown


def _settle(
    usages: list[Usage], edges: Edges, by_label: Mapping[str, UmlElement]
) -> tuple[Edges, dict[str, ModulePath | None]]:
    """The imports once the shared slots are placed, and the homes that agree with them (PD-16).

    A shared slot's home is chosen from the imports there are, and its placing adds imports, which can
    change what a module reaches: so the choice is repeated, the imports only growing, until they stop.
    """
    while True:
        homes = choose_homes(usages, reachable(edges))
        grown = _grown(edges, shared_edges(usages, homes, by_label))
        if grown == edges:
            return edges, homes
        edges = grown


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
        kinds: dict[ModulePath, str],
    ) -> None:
        self.classes, self.enums = definitions
        self.shared = shared
        self.slot_names = slot_names
        self.kinds = kinds


def _refuse_compositions(ctx: Context, model: UmlModel) -> None:
    """Task 1.4's stopgap: no composition converts silently until the tree is wired (task 1.6 deletes this)."""
    for each in model.uml_compositions or []:
        whole = ctx.class_names.get(each.whole_id, str(each.whole_id))
        part = ctx.class_names.get(each.part_id, str(each.part_id))
        ctx.findings.problem(
            UmlRule.NO_RULE, f"{whole} -> {part}", "composition: not converted yet"
        )


def _build(ctx: Context, model: UmlModel) -> tuple[list[UmlElement], list[Usage], dict[int, str]]:
    collect_elements(ctx, model)
    _refuse_compositions(ctx, model)
    elements = _generated(ctx)
    return elements, _usages(ctx, model, elements), parents(ctx, model)


def _enums(ctx: Context) -> dict[int, EnumDefinition]:
    """The enum of each enumeration; an empty one makes none but a report line (D-10)."""
    enums: dict[int, EnumDefinition] = {}
    for element in sorted(ctx.elements.values(), key=lambda each: (path_of(each), each.label)):
        built = build_enum(ctx, element) if element.is_enum else None
        if built is not None:
            enums[element.uml_class.object_id] = built
    return enums


def _slot_names(usages: list[Usage], ctx: Context) -> dict[int, list[str]]:
    names: dict[int, list[str]] = {}
    for usage in sorted(usages, key=lambda each: each.order):
        held = names.setdefault(usage.holder.uml_class.object_id, [])
        if usage.name not in held:
            held.append(usage.name)
    return names


def _module_kinds(ctx: Context, model: UmlModel, layout: Layout) -> dict[ModulePath, str]:
    """The ``module_kind`` of each module: its packages' tagged value, ``domain`` when none (#245).

    A value the toolkit's metamodel does not list is a problem naming the package. A package is its
    own module, but sibling packages of one name share a path (D-9): with different kinds that is a
    problem naming the module.
    """
    found: dict[ModulePath, set[str]] = {}
    for package in model.uml_packages or []:
        path = ctx.paths.get(package.package_id)
        if path is None or below_of(path) not in layout.names:
            continue  # a package with no class has no module
        written = ctx.tags.get(package.object_id or 0, {}).get(MODULE_KIND, DOMAIN)
        kind = package_kind(ctx, package.name, written)
        if kind is not None:
            found.setdefault(below_of(path), set()).add(kind)
    for module, kinds in found.items():
        if len(kinds) > 1:
            ctx.findings.problem(
                UmlRule.PACKAGE_MODULE,
                layout.names[module],
                f"its packages have the kinds {' and '.join(sorted(kinds))}",
            )
    return {module: min(kinds) for module, kinds in found.items()}


def _write_module(
    ctx: Context, name: str, path: ModulePath, built: Built, members: list[UmlElement]
) -> SchemaDefinition:
    settings = ctx.settings
    first = path[-1] if path else settings.subtree_package.rsplit(PATH_SEPARATOR, 1)[-1]
    note = next((ctx.paths[i].note for i in ctx.paths if below_of(ctx.paths[i]) == path), None)
    schema = SchemaDefinition(
        id=settings.schema_base + name,
        name=name,
        title=title_for(first),
        description=(note or "").replace("\r\n", "\n").strip()
        or f"The {first} package of the {settings.root_name} model, converted from UML.",
        annotations={MODULE_KIND: annotation(MODULE_KIND, built.kinds.get(path, DOMAIN))},
    )
    for element in members:
        _place(schema, element, built)
    for slot_name, slot in sorted(built.shared.definitions.items()):
        if built.shared.home[slot_name] == name:
            schema.slots[slot_name] = slot
    return schema


def _place(schema: SchemaDefinition, element: UmlElement, built: Built) -> None:
    key = element.uml_class.object_id
    if element.is_enum:
        schema.enums[element.label] = built.enums[key]
        return
    definition = built.classes[key]
    definition.slots = built.slot_names.get(key, [])
    definition.slot_usage = built.shared.class_usage.get(element.label, {})
    schema.classes[element.label] = definition


def _toolkit_imports(ctx: Context, members: list[ClassDefinition]) -> set[str]:
    """The module of each toolkit class a module's classes use as ``is_a`` or mixin (PD-17)."""
    used = {name for each in members for name in [each.is_a, *each.mixins] if name}
    return {ctx.toolkit.module_of(name) for name in used if ctx.toolkit.class_by_name(name)}


def _imports(
    ctx: Context, name: str, members: list[UmlElement], built: Built, refs: set[str]
) -> list[str]:
    classes = [built.classes[each.uml_class.object_id] for each in members if not each.is_enum]
    toolkit = {ANNOTATIONS_IMPORT} | _toolkit_imports(ctx, classes)
    toolkit.update(*(built.shared.toolkit_imports.get(each.label, set()) for each in members))
    return [LINKML_TYPES, *sorted(toolkit), *sorted(refs - {name})]


def _classes(
    ctx: Context, elements: list[UmlElement], usages: list[Usage], parent_of: Mapping[int, str]
) -> dict[int, ClassDefinition]:
    """The class of each UML class; a part is a class an owned slot ranges over (PD-13, PD-17)."""
    defaults = check_default_mixins(ctx)
    owned = {usage.shape.range for usage in usages if is_owned(usage.shape)}
    return {
        e.uml_class.object_id: build_class(
            ctx,
            e,
            parent_of.get(e.uml_class.object_id),
            e.label in owned and not is_boundary_root(e),
            defaults,
        )
        for e in elements
        if not e.is_enum
    }


def _lay_out(
    ctx: Context, elements: list[UmlElement], usages: list[Usage], parent_of: Mapping[int, str]
) -> tuple[Layout, SharedSlots]:
    """The modules the packages are written as, and the slots each of them defines or shares (R-24, PD-8)."""
    by_label = {element.label: element for element in elements}
    edges, homes = _settle(usages, _references(elements, usages, parent_of), by_label)
    names = _module_names(ctx, {path_of(element) for element in elements})
    module_of = {element.uml_class.object_id: names[path_of(element)] for element in elements}
    named_homes = {name: names[path] if path else None for name, path in homes.items()}
    lineage = (parent_of, {element.label: element.uml_class.object_id for element in elements})
    return Layout(elements, edges, names), share(ctx, usages, module_of, named_homes, lineage)


def convert(
    model: UmlModel, settings: UmlSettings, toolkit: Toolkit
) -> tuple[list[SchemaDefinition], list[ReportLine], list[CheckProblem], dict[str, str]]:
    """Convert the subtree of ``model`` into a root schema and one module per package.

    Returns the schemas (root first, then the modules by path), the report lines, the problems, each
    sorted, and the other files to write (PD-8): a path relative to ``--out`` to its text, empty when
    nothing is drawn. With any problem the schemas and the files are empty: nothing is to be written.
    """
    prefixes = {each.prefix_name: each.namespace for each in settings.prefixes or []}
    ctx = Context(settings, toolkit, prefixes)
    ctx.paths = package_paths(model, settings)
    elements, usages, parent_of = _build(ctx, model)
    toolkit_usages, usages = split_toolkit(ctx, usages)
    name_slots(ctx, usages, toolkit_usages)
    if not ctx.elements and not ctx.findings.problems():
        ctx.findings.problem(
            UmlRule.PACKAGE_MODULE,
            settings.subtree_package,
            "the package holds no class or enumeration to convert",
        )
    layout, shared = _lay_out(ctx, elements, usages, parent_of)
    mark_abstract_roots(ctx, {usage.shape.range for usage in usages}, parent_of)
    classes = _classes(ctx, elements, usages, parent_of)
    kinds = _module_kinds(ctx, model, layout)
    built = Built((classes, _enums(ctx)), shared, _slot_names(usages, ctx), kinds)
    use_toolkit_slots(ctx, toolkit_usages, classes, shared, built.slot_names)
    entries = role_entries(ctx, model)
    workflows = workflow_entries(ctx, model, {each.role for each in entries})
    problems = ctx.findings.problems()
    if problems:
        return [], ctx.findings.report(), problems, {}
    schemas = _assemble(ctx, layout, built)
    files = workflow_files(workflows)
    if entries:
        files[f"{settings.root_name}{ROLES_SUFFIX}"] = roles_file_text(entries)
    return schemas, ctx.findings.report(), [], files


def _assemble(ctx: Context, layout: Layout, built: Built) -> list[SchemaDefinition]:
    """The root schema first, then each module by path, with its imports."""
    modules: list[SchemaDefinition] = []
    for path in sorted(layout.names):
        name = layout.names[path]
        members = layout.members(path)
        schema = _write_module(ctx, name, path, built, members)
        schema.imports = _imports(ctx, name, members, built, layout.refers_to(path))
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
