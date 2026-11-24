"""The boundary check (task 1.7, PD-23): what each aggregate owns, what it refers to, who imports whom."""

from collections.abc import Iterator
from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.core.domain.generated.rp_core import ModuleKind, RpAnnotation
from rdf_persistence.schema.services.schema import PACKAGE, PACKAGE_DIR
from rdf_persistence.schema.services.schema_structure import (
    ACTIVITY,
    AGGREGATE_ROOT,
    aggregate_roots,
    annotation,
    declared_slots,
    is_owned,
    is_tenant_root,
    is_toolkit_schema,
    own_classes,
    own_schemas,
    owned_classes,
)
from rdf_persistence_generation.config import TOOLKIT_ROOTS
from rdf_persistence_generation.generated.rp_generation import (
    BoundaryRule,
    CheckProblem,
    TargetKind,
)
from rdf_persistence_generation.problems import rule_problem

# Classes reached by IRI, never owned (PD-23).
REFERENCE_CLASSES = ("Principal", ACTIVITY)
VALUE = ModuleKind.VALUE.value


_NO_TECHNICAL_OR_ACCESS = (ModuleKind.TECHNICAL.value, ModuleKind.ACCESS.value)
# DEC-3, by the module's own kind: (the kinds it must not import, the hint appended to the problem).
# A plain mapping, not a class: the repository declares data classes in LinkML.
IMPORT_RULES: dict[str, tuple[tuple[str, ...], str]] = {
    ModuleKind.DOMAIN.value: (_NO_TECHNICAL_OR_ACCESS, ""),
    VALUE: (_NO_TECHNICAL_OR_ACCESS, ": move the class into a value or domain module"),
}
NEVER_STORED = (ModuleKind.TECHNICAL.value, VALUE)  # the kinds whose classes no root owns

# PD-4: the folder before ``generated`` that each target kind allows, and the packages outside the themes.
GENERATED = "generated"
DOMAIN_FOLDERS = ("domain",)
TECHNICAL_FOLDERS = ("services", "adapters", "entrypoints")
LAYER_FOLDERS = DOMAIN_FOLDERS + TECHNICAL_FOLDERS
THEME_PATH = (PACKAGE,)  # a theme sits directly under the library package
FOLDER_EXEMPT = ("rdf_persistence.testkit", "rdf_persistence_generation")


def _kind_of(schema: SchemaDefinition) -> str | None:
    return annotation(schema, RpAnnotation.MODULE_KIND)


def technical_classes(schemas: list[SchemaDefinition]) -> list[ClassDefinition]:
    """The classes that are never stored: those of the modules annotated ``module_kind: technical`` or ``value``.

    The name stays for the callers that read it as "exempt from the stored-class rules" (D-1); a class is
    told apart by object, not by name.
    """
    return [
        cls
        for schema in schemas
        if _kind_of(schema) in NEVER_STORED
        for cls in schema.classes.values()
    ]


def _is_activity(view: SchemaView, class_name: str) -> bool:
    return ACTIVITY in view.class_ancestors(class_name)


def _use_cases(view: SchemaView, classes: list[ClassDefinition]) -> set[str]:
    """A use case is a message, never stored by itself (PD-20), so it needs no owner."""
    return {cls.name for cls in classes if _is_activity(view, cls.name)}


def _ownership_problems(
    view: SchemaView, classes: list[ClassDefinition], technical: list[ClassDefinition]
) -> Iterator[CheckProblem]:
    """Technical classes are exempt, and what they own does not count: a request shape is never stored."""
    exempt = {id(cls) for cls in technical}
    stored = [cls for cls in classes if id(cls) not in exempt]
    roots = {root.name for root in aggregate_roots(view, classes)}
    kept = roots | owned_classes(view, stored) | _use_cases(view, stored)
    for cls in stored:
        if cls.mixin or cls.abstract or cls.name in kept or is_tenant_root(cls):
            continue
        yield rule_problem(
            BoundaryRule.OWNERSHIP, cls.name, "is neither an aggregate root nor owned by any root"
        )


def _may_be_referred_to(view: SchemaView, range_: str) -> bool:
    ancestors = view.class_ancestors(range_)
    return AGGREGATE_ROOT in ancestors or any(name in ancestors for name in REFERENCE_CLASSES)


def _reference_problems(
    view: SchemaView, classes: list[ClassDefinition], homes: dict[str, tuple[str, str]]
) -> Iterator[CheckProblem]:
    """A slot over a never-stored class is the holding rule's to report, so it is skipped here (D-2)."""
    for cls in classes:
        induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
        for name in sorted(declared_slots(cls) & induced.keys()):
            slot = induced[name]
            is_class_range = slot.range in view.all_classes() and str(slot.range) not in homes
            if is_class_range and not is_owned(slot) and not _may_be_referred_to(view, slot.range):
                yield rule_problem(
                    BoundaryRule.REFERENCE,
                    name,
                    f"of {cls.name} points to {slot.range}, which is neither a root nor a reference class: "
                    f"annotate the slot owned: true to hold {slot.range} inline, "
                    f"or make {slot.range} an aggregate root, "
                    "or point the slot at a root, Principal or Activity",
                )


def _direction_problems(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[CheckProblem]:
    """PD-20: the stored model never refers to a use case, so a slot of a class that is not an activity does not range over one."""
    names = {cls.name for cls in classes}
    use_cases = {
        name
        for name in names
        if _is_activity(view, name) and AGGREGATE_ROOT not in view.class_ancestors(name)
    }
    for cls in classes:
        if _is_activity(view, cls.name):
            continue
        induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
        for name in sorted(declared_slots(cls) & induced.keys()):
            if induced[name].range in use_cases:
                yield rule_problem(
                    BoundaryRule.ACTIVITY_DIRECTION,
                    name,
                    f"of {cls.name} ranges over {induced[name].range}, a use case: the stored model "
                    "does not refer to the activities module; "
                    "range over Activity, or move the slot to the activity class",
                )


def module_name(entry: str) -> str:
    """The module an ``imports`` entry names: its last segment, without a path or a prefix."""
    return entry.split("/")[-1].split(":")[-1]


def _imported(view: SchemaView, schema: SchemaDefinition) -> Iterator[SchemaDefinition]:
    by_name = {other.name: other for other in view.schema_map.values()}
    for imported in schema.imports:
        found = by_name.get(module_name(imported))
        if found is not None:
            yield found


def _module_problems(view: SchemaView, schemas: list[SchemaDefinition]) -> Iterator[CheckProblem]:
    """A domain or value module imports no technical or access module (DEC-3); a value one is told where to go."""
    for schema in schemas:
        own_kind = _kind_of(schema)
        if (rule := IMPORT_RULES.get(own_kind or "")) is None:
            continue
        forbidden, hint = rule
        for imported in _imported(view, schema):
            kind = annotation(imported, RpAnnotation.MODULE_KIND)
            if kind in forbidden:
                yield rule_problem(
                    BoundaryRule.MODULE_KIND,
                    schema.name,
                    f"is a {own_kind} module and imports {imported.name}, a {kind} module{hint}",
                )


def _is_technical(schema: SchemaDefinition) -> bool:
    return annotation(schema, RpAnnotation.MODULE_KIND) == ModuleKind.TECHNICAL.value


def never_stored_homes(view: SchemaView) -> dict[str, tuple[str, str]]:
    """Class name to (module name, module kind) for every class of a technical or value module of the view.

    Read over the whole import closure, not one target's own modules: a value module in a folder of its
    own is another target's, yet a stored class must not hold its classes either (D-2).
    """
    view.imports_closure()
    return {
        str(cls.name): (str(schema.name), str(_kind_of(schema)))
        for schema in view.schema_map.values()
        if _kind_of(schema) in NEVER_STORED
        for cls in schema.classes.values()
    }


def _held_slots(
    view: SchemaView, cls: ClassDefinition, homes: dict[str, tuple[str, str]]
) -> Iterator[tuple[str, str]]:
    """The (slot, range) pairs of the slots ``cls`` declares that range over a never-stored class."""
    induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
    for name in sorted(declared_slots(cls) & induced.keys()):
        if str(induced[name].range) in homes:
            yield name, str(induced[name].range)


WHY_NOT_HELD = {
    ModuleKind.TECHNICAL.value: "only a technical module holds a technical class",
    VALUE: "a stored class never holds a value",
}


def _may_hold(holder: str | None, held: str) -> bool:
    """A technical module holds anything; a value module holds a value; the rest hold neither (DEC-5)."""
    return holder == ModuleKind.TECHNICAL.value or (holder == VALUE and held == VALUE)


def _held_ancestors(
    view: SchemaView, cls: ClassDefinition, homes: dict[str, tuple[str, str]]
) -> Iterator[str]:
    """The never-stored classes ``cls`` extends by ``is_a`` or ``mixins``: a stored class inherits them whole."""
    for ancestor in view.class_ancestors(cls.name, reflexive=False):
        if str(ancestor) in homes:
            yield str(ancestor)


def _holding_problems(
    view: SchemaView, schemas: list[SchemaDefinition], homes: dict[str, tuple[str, str]]
) -> Iterator[CheckProblem]:
    """D-55 (4), DEC-5: a stored module never holds a technical or value class, by a slot or by inheritance."""
    for schema in schemas:
        kind = _kind_of(schema)
        for cls in schema.classes.values():
            held_by = [
                (held, f"in the slot {name} of {cls.name}")
                for name, held in _held_slots(view, cls, homes)
            ] + [
                (held, f"as an ancestor of {cls.name}")
                for held in _held_ancestors(view, cls, homes)
            ]
            for held, where in held_by:
                home, held_kind = homes[held]
                if _may_hold(kind, held_kind):
                    continue
                yield rule_problem(
                    BoundaryRule.MODULE_KIND,
                    schema.name,
                    f"is a module of {kind or 'no'} kind and holds {held}, a class of the {held_kind} "
                    f"module {home}, {where}: {WHY_NOT_HELD[held_kind]}",
                )


def _never_stored_root_problems(
    view: SchemaView, schemas: list[SchemaDefinition]
) -> Iterator[CheckProblem]:
    """D-55 (4), DEC-2: a technical or value class is never stored, so it declares no root."""
    for kind in NEVER_STORED:
        never_stored = technical_classes([s for s in schemas if _kind_of(s) == kind])
        roots = {root.name for root in aggregate_roots(view, never_stored)}
        for cls in never_stored:
            if cls.name in roots or is_tenant_root(cls):
                yield rule_problem(
                    BoundaryRule.MODULE_KIND,
                    cls.name,
                    f"is an aggregate root in a {kind} module: a {kind} class is never stored, "
                    "so it declares no root",
                )


def derived_kind(view: SchemaView, folder: Path) -> TargetKind:
    """The kind of the target that generates ``folder`` (PD-1): technical when every own module is."""
    schemas = own_schemas(view, folder)
    if schemas and all(_is_technical(schema) for schema in schemas):
        return TargetKind.TECHNICAL
    return TargetKind.DOMAIN


def mixed_kind_problems(view: SchemaView, folder: Path) -> list[CheckProblem]:
    """A target generates one kind: technical modules beside others are refused (PD-2)."""
    schemas = own_schemas(view, folder)
    technical = [schema.name for schema in schemas if _is_technical(schema)]
    if not technical or len(technical) == len(schemas):
        return []
    message = (
        f"generates technical modules {','.join(technical)} beside domain ones: "
        "a target generates one kind"
    )
    return [rule_problem(BoundaryRule.TARGET_KIND, "", message)]


def _is_exempt(package: str) -> bool:
    """Whether ``package`` is one of ``FOLDER_EXEMPT`` or inside it (whole segments, not a prefix)."""
    return any(package == p or package.startswith(f"{p}.") for p in FOLDER_EXEMPT)


def toolkit_themes() -> frozenset[str]:
    """The themes of the library: its subpackages, the testkit (outside the themes) apart.

    The package folders are the one list; a test holds it equal to the themes of ``tests.changed``,
    and the layout tests and ``themes-layered`` refuse a folder that is none.
    """
    return frozenset(
        init.parent.name
        for init in PACKAGE_DIR.glob("*/__init__.py")
        if f"{PACKAGE}.{init.parent.name}" not in FOLDER_EXEMPT
    )


def _in_a_theme(segments: list[str]) -> bool:
    """Whether ``segments`` (the package before the layer) are ``<library package>.<theme>``."""
    return (
        len(segments) == len(THEME_PATH) + 1
        and segments[:1] == list(THEME_PATH)
        and segments[1] in toolkit_themes()
    )


def _folder_message(
    package: str, kind: TargetKind, toolkit: bool, has_value: bool = False
) -> str | None:
    """What is wrong with the folder of ``package`` for a target of ``kind``; ``None`` when it fits.

    ``has_value``: a module of the target is ``module_kind: value``, so the hint says where it belongs.
    """
    allowed = DOMAIN_FOLDERS if kind == TargetKind.DOMAIN else TECHNICAL_FOLDERS
    segments = package.split(".")
    layer = segments.index(GENERATED) - 1 if GENERATED in segments else -1
    if layer < 0 or segments[layer] not in LAYER_FOLDERS:
        return f"has no layer before {GENERATED}: a {kind.value} target's package ends in <{'|'.join(allowed)}>.{GENERATED}"
    if segments[layer] not in allowed:
        hint = (
            "; if its modules are technical, annotate them module_kind: technical"
            if kind == TargetKind.DOMAIN
            else ""
        ) + ("; a value module stays in domain" if has_value else "")
        return f"is not in a folder a {kind.value} target allows: {' or '.join(allowed)} before {GENERATED}{hint}"
    if toolkit and not _in_a_theme(segments[:layer]):
        return (
            f"is not in a theme: the layer folder is {PACKAGE}.<theme>.<layer>, and the theme is one of "
            f"{', '.join(sorted(toolkit_themes()))}"
        )
    return None


def kind_folder_problems(
    folder: Path, package: str, kind: TargetKind, view: SchemaView | None = None
) -> list[CheckProblem]:
    """The ``package`` of a target that sits in a folder its ``kind`` does not allow (PD-3, DEC-3).

    The segment before ``generated`` is ``domain`` for a domain target and a technical layer for a
    technical one; a group after ``generated`` is allowed, the testkit and the generator are exempt.
    For the toolkit's own run, the one before that is also a theme of the library
    (``rdf_persistence.<theme>.<layer>``); a consumer's package has no theme to check. With the ``view``,
    a target holding a value module is told that it stays in domain.
    """
    if _is_exempt(package):
        return []
    has_value = view is not None and any(
        _kind_of(schema) == VALUE for schema in own_schemas(view, folder)
    )
    message = _folder_message(
        package, TargetKind(kind), is_toolkit_schema(folder, roots=TOOLKIT_ROOTS), has_value
    )
    return [rule_problem(BoundaryRule.TARGET_KIND, package, message)] if message else []


def boundary_problems(view: SchemaView, folder: Path) -> list[CheckProblem]:
    """Every problem of the schemas kept in ``folder``, in a stable order.

    The toolkit's own schemas get the import rule but not the class rules (PD-23), and neither do the
    classes of a module annotated ``module_kind: technical``, which are never stored (D-49).
    """
    schemas = own_schemas(view, folder)
    classes = [] if is_toolkit_schema(folder, roots=TOOLKIT_ROOTS) else own_classes(schemas)
    technical = technical_classes(schemas)
    exempt = {id(cls) for cls in technical}
    stored = [cls for cls in classes if id(cls) not in exempt]
    homes = never_stored_homes(view)
    return [
        *_ownership_problems(view, classes, technical),
        *_reference_problems(view, stored, homes),
        *_direction_problems(view, classes),
        *_module_problems(view, schemas),
        *_holding_problems(view, schemas, homes),
        *_never_stored_root_problems(view, schemas),
    ]
