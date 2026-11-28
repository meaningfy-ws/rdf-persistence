"""The toolkit classes a converted class builds on (R-10, R-25..R-28; PD-12, PD-17, PD-29; D-7).

A class gets its mixins in one order, each once: ``AggregateRoot`` first, then the ``rp_mixins`` names in tag
order, the drawn toolkit parents in connector order, the default mixins, and ``UnderWorkflow``. A toolkit
class that is not a mixin (``Activity``) is an ``is_a`` source, with the domain parent: two sources are a
problem. Which classes are toolkit classes comes from the toolkit's own metamodel, never a list here.
"""

from typing import Final

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence_generation.generated.rp_generation import UmlElement, UmlRule
from rdf_persistence_generation.uml.context import Context, is_boundary_root
from rdf_persistence_generation.uml.tags import RP_MIXINS

AGGREGATE_ROOT: Final = "AggregateRoot"
DESCRIBED: Final = "Described"
UNDER_WORKFLOW: Final = "UnderWorkflow"
RP_UNLABELLED: Final = "rp_unlabelled"
WORKFLOW: Final = RpAnnotation.WORKFLOW.value
TAG_SEPARATOR: Final = ","
TRUE: Final = "true"
DEFAULT_MIXINS_OPTION: Final = "--default-mixins"
MIXIN_TAGS: Final = (
    RP_MIXINS,
    RP_UNLABELLED,
    WORKFLOW,
)  # read here; ``rp_mixins`` has no annotation


class Composed:
    """The ``is_a`` and the ``mixins`` of a class."""

    __slots__ = ("is_a", "mixins")

    def __init__(self, is_a: str | None, mixins: list[str]) -> None:
        self.is_a = is_a
        self.mixins = mixins


def _once(names: list[str]) -> list[str]:
    return list(dict.fromkeys(names))


def _unknown(ctx: Context, element: str, name: str) -> None:
    known = ", ".join(ctx.toolkit.class_names())
    ctx.findings.problem(
        UmlRule.TOOLKIT_MIXINS,
        element,
        f"{name} is not a toolkit class; the toolkit classes are {known}",
    )


def _known(ctx: Context, element: str, names: list[str]) -> list[str]:
    """The names that are toolkit classes; each other one is a problem listing the toolkit classes."""
    found: list[str] = []
    for name in names:
        if ctx.toolkit.class_by_name(name) is None:
            _unknown(ctx, element, name)
        else:
            found.append(name)
    return found


def _listed(text: str) -> list[str]:
    return [item.strip() for item in text.split(TAG_SEPARATOR) if item.strip()]


def check_default_mixins(ctx: Context) -> list[str]:
    """The default mixins that are toolkit classes; an unknown one is a problem (PD-17)."""
    return _known(ctx, DEFAULT_MIXINS_OPTION, list(ctx.settings.default_mixins or []))


def _is_mixin(ctx: Context, name: str) -> bool:
    return bool(ctx.toolkit.toolkit_class(name).mixin)


def _defaults(ctx: Context, element: UmlElement, owned: bool, defaults: list[str]) -> list[str]:
    """The default mixins of a root or an owned part; an unlabelled part has ``Described`` only (PD-29)."""
    if is_boundary_root(element):
        return defaults
    if not owned:
        return []
    tags = ctx.tags.get(element.uml_class.object_id, {})
    if tags.get(RP_UNLABELLED, "").strip().lower() == TRUE:
        return [each for each in defaults if each == DESCRIBED]
    return defaults


def _mixins(
    ctx: Context, element: UmlElement, named: list[str], owned: bool, defaults: list[str]
) -> list[str]:
    """The mixins of a class, in the order of the module docstring."""
    mixins = [AGGREGATE_ROOT] if element.is_root or element.is_abstract_root else []  # R-10, R-23
    mixins += [name for name in named if _is_mixin(ctx, name)]
    mixins += _defaults(ctx, element, owned, defaults)
    if ctx.tags.get(element.uml_class.object_id, {}).get(WORKFLOW, "").strip():
        mixins.append(UNDER_WORKFLOW)
    return mixins


def compose(
    ctx: Context, element: UmlElement, domain_parent: str | None, owned: bool, defaults: list[str]
) -> Composed:
    """The ``is_a`` and the mixins of a class; two ``is_a`` sources are a problem naming the class (PD-17).

    ``owned`` is whether the composition tree makes the class a part; ``defaults`` are the
    default mixins that are toolkit classes (``check_default_mixins``).
    """
    tags = ctx.tags.get(element.uml_class.object_id, {})
    named = _known(ctx, element.label, _listed(tags.get(RP_MIXINS, "")))
    named += ctx.drawn_parents.get(element.uml_class.object_id, [])
    mixins = _mixins(ctx, element, named, owned, defaults)
    sources = [domain_parent] if domain_parent else []
    sources += [name for name in named if not _is_mixin(ctx, name)]
    sources = _once(sources)
    if len(sources) > 1:
        ctx.findings.no_rule(element.label, f"two is_a sources, {' and '.join(sources)}")
        sources = sources[:1]
    return Composed(sources[0] if sources else None, _once(mixins))
