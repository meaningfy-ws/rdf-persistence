"""Classes and enumerations (R-2, R-3, R-4, R-7, R-9, R-10, R-12, R-19; PD-6, PD-9..PD-12, PD-15; D-10, D-13, D-14).

``collect_elements`` decides which UML classes are generated; ``build_class`` and ``build_enum`` write
their LinkML definitions; ``parents`` reads the generalisations. Slots are in ``slots``.
"""

from collections.abc import Mapping

from linkml_runtime.linkml_model import (
    Annotation,
    ClassDefinition,
    EnumDefinition,
    PermissibleValue,
)

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    ReportKind,
    UmlClass,
    UmlElement,
    UmlLinkKind,
    UmlModel,
    UmlName,
    UmlRule,
)
from rdf_persistence_generation.uml.context import (
    LEFT_EXCLUDED,
    LEFT_NOT_GENERATED,
    LEFT_OUTSIDE,
    Context,
    below_of,
    local_of,
)
from rdf_persistence_generation.uml.mixins import RP_MIXINS, compose
from rdf_persistence_generation.uml.naming import (
    CURIE_SEPARATOR,
    check_class_name,
    check_slot_name,
    permissible_value_key,
    rp_path_for,
    title_for,
)
from rdf_persistence_generation.uml.tags import GRAPH, apply_tags

CLASS_TYPE = "Class"
ENUMERATION_TYPE = "Enumeration"
ROOT_STEREOTYPE = "root"
TENANT_STEREOTYPE = "tenant root"
ABSTRACT_STEREOTYPE = "abstract"
RP_PATH = "rp_path"
META = "meta"
EMPTY_LIST_NOTE = "no literals; its list is kept outside the model, so slots range over a URI"


def description_of(note: str | None) -> str | None:
    """A note as a description: line ends as ``\\n``, outer whitespace stripped, nothing when empty (PD-11)."""
    text = (note or "").replace("\r\n", "\n").strip()
    return text or None


def annotation(tag: str, value: str) -> Annotation:
    return Annotation(tag=tag, value=value)


def _stereotype(uml: UmlClass) -> str:
    return (uml.uml_stereotype or "").strip()


def _admit(ctx: Context, uml: UmlClass, path: tuple[str, ...]) -> None:
    label, stereotype = local_of(uml.name), _stereotype(uml)
    if uml.object_type not in (CLASS_TYPE, ENUMERATION_TYPE):
        ctx.findings.no_rule(label, f"object type {uml.object_type}")
    elif uml.multiple_stereotypes:
        ctx.findings.no_rule(label, "more than one stereotype")
    elif uml.object_type == CLASS_TYPE and ctx.toolkit_name(uml.name) is not None:
        _use_drawn_toolkit_class(ctx, uml, label)
    elif stereotype in (ctx.settings.not_generated_stereotypes or []):
        _leave_out(ctx, uml, LEFT_NOT_GENERATED)
        ctx.findings.note(
            ReportKind.NOT_GENERATED, label, f"stereotype {stereotype}, not generated"
        )
    elif stereotype.lower() not in ("", ROOT_STEREOTYPE, TENANT_STEREOTYPE, ABSTRACT_STEREOTYPE):
        ctx.findings.no_rule(label, f"stereotype {stereotype}")
    else:
        _register(ctx, uml, path)


def _use_drawn_toolkit_class(ctx: Context, uml: UmlClass, label: str) -> None:
    """A toolkit class drawn inside the subtree is the toolkit's, not generated; a parent only (PD-17, R-28)."""
    toolkit_class = str(ctx.toolkit_name(uml.name))
    _leave_out(ctx, uml, LEFT_NOT_GENERATED)
    ctx.drawn_toolkit[uml.object_id] = toolkit_class
    ctx.findings.note(
        ReportKind.NOT_GENERATED, label, f"drawn as the toolkit's {toolkit_class}, not generated"
    )


def _leave_out(ctx: Context, uml: UmlClass, why: str) -> None:
    ctx.left_out[uml.object_id] = why
    if why == LEFT_NOT_GENERATED and uml.object_type == ENUMERATION_TYPE:
        ctx.left_out_enums.add(uml.object_id)


def _register(ctx: Context, uml: UmlClass, path: tuple[str, ...]) -> None:
    name = ctx.resolve(uml.name, uml.name)
    if name is None:
        return
    problem = check_class_name(name.name, local_of(uml.name))
    if problem is not None:
        ctx.findings.add(problem)
        return
    stereotype = _stereotype(uml).lower()
    ctx.elements[uml.object_id] = UmlElement(
        uml_class=uml,
        resolved_name=name,
        label=name.name,
        module_path=list(path),
        is_enum=uml.object_type == ENUMERATION_TYPE,
        is_root=stereotype == ROOT_STEREOTYPE,
        is_abstract=bool(uml.is_abstract) or stereotype == ABSTRACT_STEREOTYPE,
        is_tenant_root=stereotype == TENANT_STEREOTYPE,
    )


def _collect_outside(ctx: Context, model: UmlModel) -> None:
    """The classes the reader found at a link's far end: excluded when their package is, else outside (D-17)."""
    for uml in model.uml_outside_classes or []:
        path = ctx.paths.get(uml.package_id)
        _leave_out(
            ctx, uml, LEFT_EXCLUDED if path is not None and path.is_excluded else LEFT_OUTSIDE
        )
        ctx.class_names[uml.object_id] = local_of(uml.name)
        toolkit_class = ctx.toolkit_name(uml.name)
        if toolkit_class is not None:
            ctx.drawn_toolkit[uml.object_id] = toolkit_class  # R-28: not generated, a parent only


def collect_elements(ctx: Context, model: UmlModel) -> None:
    """Classify every class of the subtree: generated, left out, or a problem; check names for clashes."""
    for tagged in model.uml_tagged_values or []:
        held = ctx.tags.setdefault(tagged.owner_id, {})
        value = tagged.tag_value or ""
        held[tagged.name] = (
            f"{held[tagged.name]},{value}"
            if tagged.name == RP_MIXINS and tagged.name in held
            else value
        )
        ctx.tag_values.setdefault(tagged.owner_id, {}).setdefault(tagged.name, []).append(value)
    _collect_outside(ctx, model)
    for uml in sorted(model.uml_classes or [], key=lambda each: (each.name, each.object_id)):
        ctx.class_names[uml.object_id] = local_of(uml.name)
        path = ctx.paths.get(uml.package_id)
        if path is None:
            continue
        if path.is_excluded:
            _leave_out(ctx, uml, LEFT_EXCLUDED)
        else:
            _admit(ctx, uml, below_of(path))
    _check_clashes(ctx)
    _check_root_paths(ctx)


def _iri_of(ctx: Context, name: UmlName) -> str:
    return name.iri or ctx.default_namespace() + name.name


def _check_clashes(ctx: Context) -> None:
    seen: dict[str, UmlElement] = {}
    for element in sorted(ctx.elements.values(), key=lambda each: each.uml_class.object_id):
        first = seen.setdefault(element.label, element)
        if first is not element:
            iris = sorted((_iri_of(ctx, first.resolved_name), _iri_of(ctx, element.resolved_name)))
            ctx.findings.problem(
                UmlRule.CLASS_IRI,
                element.label,
                f"{iris[0]} and {iris[1]} both map to {element.label}",
            )
    _check_toolkit_names(ctx)


def _check_toolkit_names(ctx: Context) -> None:
    """A domain class named like a toolkit class, with another IRI, is a problem naming both (PD-6, S-11)."""
    for element in sorted(ctx.elements.values(), key=lambda each: each.uml_class.object_id):
        if element.is_enum or ctx.toolkit.class_by_name(element.label) is None:
            continue
        iris = sorted((_iri_of(ctx, element.resolved_name), ctx.toolkit.class_uri(element.label)))
        if iris[0] != iris[1]:
            ctx.findings.problem(
                UmlRule.CLASS_IRI,
                element.label,
                f"{iris[0]} and {iris[1]} both map to {element.label}",
            )


def root_path(ctx: Context, element: UmlElement) -> str:
    """The ``rp_path`` of a root: its tagged value, else the plural of its name in kebab case (PD-12)."""
    return ctx.tags.get(element.uml_class.object_id, {}).get(RP_PATH) or rp_path_for(element.label)


def _check_root_paths(ctx: Context) -> None:
    seen: dict[str, UmlElement] = {}
    for element in sorted(ctx.elements.values(), key=lambda each: each.label):
        if not element.is_root:
            continue
        path = root_path(ctx, element)
        first = seen.setdefault(path, element)
        if first is not element:
            ctx.findings.problem(
                UmlRule.ROOT_CLASS,
                first.label,
                f"rp_path {path} is used by {first.label} and {element.label}",
            )


def class_uri_of(ctx: Context, name: UmlName) -> str | None:
    """The explicit IRI of a class or enum: none when it is the implicit one or the name is unprefixed (D-14)."""
    if name.curie is None or name.iri == ctx.default_namespace() + name.name:
        return None
    return name.curie


def _note_tags(ctx: Context, element: UmlElement, skip: tuple[str, ...]) -> None:
    for tag_name in sorted(ctx.tags.get(element.uml_class.object_id, {})):
        if tag_name not in skip:
            ctx.findings.note(
                ReportKind.IGNORED_TAG, element.label, f"tagged value {tag_name} is not used"
            )


def _described(ctx: Context, element: UmlElement) -> str | None:
    description = description_of(element.uml_class.note)
    if description is None:
        ctx.findings.note(ReportKind.NO_NOTE, element.label, "no note, so no description")
    return description


def build_class(
    ctx: Context, element: UmlElement, parent: str | None, owned: bool, defaults: list[str]
) -> ClassDefinition:
    """The class of a UML class: title, description, IRI, abstract flag, parent, mixins and the root's path.

    ``parent`` is the domain parent; ``owned`` whether a boundary or composite makes the class a part;
    ``defaults`` the default mixins (PD-17).
    """
    composed = compose(ctx, element, parent, owned, defaults)
    definition = ClassDefinition(
        name=element.label,
        title=title_for(element.label, element.uml_class.uml_alias),
        description=_described(ctx, element),
        class_uri=class_uri_of(ctx, element.resolved_name),
        is_a=composed.is_a,
        mixins=composed.mixins,
    )
    if element.is_abstract:
        definition.abstract = True
    derived: dict[str, Annotation] = {}
    if element.is_root:
        derived[RP_PATH] = annotation(RP_PATH, root_path(ctx, element))
    if element.is_tenant_root:
        derived[GRAPH] = annotation(GRAPH, META)
        _check_tenant_graph(ctx, element)
    apply_tags(ctx, element, definition, derived)
    return definition


def _check_tenant_graph(ctx: Context, element: UmlElement) -> None:
    """A tenant root lives in the meta graph, so a ``graph`` tag of another value is a problem (R-18)."""
    written = ctx.tags.get(element.uml_class.object_id, {}).get(GRAPH)
    if written is not None and written.strip().lower() != META:
        ctx.findings.problem(
            UmlRule.TENANT_ROOT,
            element.label,
            f"graph: {written!r} conflicts with the «tenant root» stereotype, which is graph {META}",
        )


def parents(ctx: Context, model: UmlModel) -> dict[int, str]:
    """The domain parent of each class (PD-9, PD-30); others are problems.

    A generalisation to a drawn toolkit class is kept in ``ctx.drawn_parents`` for the mixins (R-28).
    """
    found: dict[int, list[int]] = {}
    for each in sorted(model.uml_links or [], key=lambda link: link.connector_id):
        if each.link_kind != UmlLinkKind.GENERALISATION or each.source_id not in ctx.elements:
            continue
        child = ctx.elements[each.source_id]
        if child.is_enum:
            ctx.findings.no_rule(child.label, "generalisation from an enumeration")
        elif each.target_id in ctx.drawn_toolkit:
            ctx.drawn_parents.setdefault(each.source_id, []).append(
                ctx.drawn_toolkit[each.target_id]
            )
        else:
            found.setdefault(each.source_id, []).append(each.target_id)
    return {
        child: name
        for child, targets in found.items()
        if (name := _one_parent(ctx, ctx.elements[child], targets)) is not None
    }


def _concrete_below(
    label: str, children: dict[str, list[UmlElement]], seen: set[str]
) -> list[UmlElement]:
    """The concrete classes that descend from ``label`` through any number of abstract ones."""
    found: list[UmlElement] = []
    for child in children.get(label, []):
        if child.label in seen:
            continue
        seen.add(child.label)
        found += _concrete_below(child.label, children, seen) if child.is_abstract else [child]
    return found


def mark_abstract_roots(ctx: Context, ranges: set[str], parent_of: Mapping[int, str]) -> None:
    """Mark the abstract roots (R-23, PD-19).

    An abstract class is one when it is the range of a generated slot (``ranges``), has concrete descendants
    and all of them are «root».
    """
    children: dict[str, list[UmlElement]] = {}
    for element in ctx.elements.values():
        parent = parent_of.get(element.uml_class.object_id)
        if parent is not None:
            children.setdefault(parent, []).append(element)
    for element in ctx.elements.values():
        if element.is_enum or not element.is_abstract or element.is_root:
            continue
        below = _concrete_below(element.label, children, {element.label})
        element.is_abstract_root = (
            element.label in ranges and bool(below) and all(each.is_root for each in below)
        )


def _parent_label(ctx: Context, target: int) -> str | None:
    element = ctx.elements.get(target)
    return element.label if element is not None and not element.is_enum else None


def _one_parent(ctx: Context, child: UmlElement, targets: list[int]) -> str | None:
    labels = [_parent_label(ctx, target) for target in targets]
    if len(targets) > 1:
        ctx.findings.no_rule(child.label, "two or more parent classes")
    elif labels[0] is None:
        ctx.findings.no_rule(child.label, "generalisation to a class that is not converted")
    else:
        return labels[0]
    return None


def _literal_meaning(ctx: Context, enum: UmlElement, literal: str) -> str | None:
    if CURIE_SEPARATOR not in literal:
        meaning = f"{ctx.settings.default_prefix}:{literal}"
        ctx.findings.note(
            ReportKind.IMPLICIT_MEANING,
            f"{enum.label}.{literal}",
            f"written without a prefix; meaning {meaning}",
        )
        return meaning
    name = ctx.resolve(literal, f"{enum.label}.{local_of(literal)}")
    return name.curie if name is not None else None


def _permissible_value(
    ctx: Context, enum: UmlElement, literal: str, note: str | None
) -> PermissibleValue | None:
    element = f"{enum.label}.{local_of(literal)}"
    description = description_of(note)
    if description is None:
        ctx.findings.note(ReportKind.NO_NOTE, element, "no note, so no description")
    meaning = _literal_meaning(ctx, enum, literal)
    key = permissible_value_key(literal)
    problem: CheckProblem | None = check_slot_name(key, element)
    if problem is not None or meaning is None:
        if problem is not None:
            ctx.findings.add(problem)
        return None
    return PermissibleValue(
        text=key,
        title=title_for(literal.rsplit(":", 1)[-1]),
        description=description,
        meaning=meaning,
    )


def build_enum(ctx: Context, element: UmlElement) -> EnumDefinition | None:
    """The enum of a UML enumeration, its literals in position order; none for an empty one (D-10)."""
    literals = sorted(
        element.uml_class.uml_attributes or [], key=lambda each: (each.position or 0, each.name)
    )
    if not literals:
        ctx.findings.note(ReportKind.EXTERNAL_LIST, element.label, EMPTY_LIST_NOTE)
        return None
    values: dict[str, PermissibleValue] = {}
    for literal in literals:
        value = _permissible_value(ctx, element, literal.name, literal.note)
        if value is None:
            continue
        if value.text in values:
            ctx.findings.problem(
                UmlRule.ENUMERATION, element.label, f"two literals have the key {value.text}"
            )
        values[value.text] = value
    _note_tags(ctx, element, ())
    return EnumDefinition(
        name=element.label,
        title=title_for(element.label, element.uml_class.uml_alias),
        description=_described(ctx, element),
        permissible_values=values,
    )
