"""The composition tree and the derived roots, a pure pass (PD-2, PD-4..PD-6, PD-8, PD-19; D-6).

``derive_aggregates`` takes the records the converter has read and returns one ``UmlAggregates``: the
derived roots, the tree as rows, the tops that reach each part class, the owned ends, the classes left
inside an own graph and the findings. It never reads or fills a ``Context`` (PD-19, pinned by
``test_uml_pass_signatures``). ``package_kinds`` reads each package's ``module_kind`` before it.

Two inputs go beyond PD-19's list, both what ``Context`` holds today: ``drawn_toolkit`` (which of the
classes left out are the toolkit's, PD-8 refuses them as an end) and ``class_names`` (the name of a
class that is no element, for a message).
"""

from collections.abc import Mapping
from typing import Final

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    LeftOutReason,
    ReportKind,
    ReportLine,
    UmlAggregates,
    UmlComposition,
    UmlElement,
    UmlLink,
    UmlLinkKind,
    UmlOwnedEnd,
    UmlPackage,
    UmlPartOf,
    UmlReach,
    UmlRule,
    UmlTaggedValue,
)
from rdf_persistence_generation.uml.context import local_of

MODULE_KIND: Final = "module_kind"
DOMAIN: Final = "domain"
OWN_GRAPH: Final = "own graph"
DIRECTED: Final = "Source -> Destination"
BIDIRECTIONAL: Final = "Bi-Directional"
ARROW: Final = "→"
NO_RULE_TAIL: Final = "no rule converts it"


def package_kinds(packages: list[UmlPackage], tags: list[UmlTaggedValue]) -> dict[int, str]:
    """The ``module_kind`` of each package, from the tagged value of its object; ``domain`` when none (A-5).

    It reports nothing: the kind is read case-blind and a value the metamodel does not list is kept as
    written, ``convert._module_kinds`` is where it is refused.
    """
    written = {
        tag.owner_id: (tag.tag_value or "").strip().lower()
        for tag in tags
        if tag.name == MODULE_KIND
    }
    return {
        package.package_id: written.get(package.object_id or 0) or DOMAIN for package in packages
    }


class _End:
    """One end of an association that may give a slot: the holder, the class it ranges over, its role."""

    def __init__(self, link_id: int, holder_id: int, other_id: int, role: str) -> None:
        self.link_id = link_id
        self.holder_id = holder_id
        self.other_id = other_id
        self.role = role


def _ends(links: list[UmlLink]) -> list[_End]:
    """The slot-giving ends of the associations a direction accepts (links.py ``_ends`` and ``_wrong_direction``)."""
    return [
        end
        for link in sorted(links, key=lambda each: each.connector_id)
        if _accepted(link)
        for end in _link_ends(link)
    ]


def _accepted(link: UmlLink) -> bool:
    """Whether an association is plain and its direction is one the converter takes."""
    if link.link_kind != UmlLinkKind.ASSOCIATION or link.uml_stereotype or link.association_class:
        return False
    return link.direction == BIDIRECTIONAL or (link.direction == DIRECTED and not link.source_role)


def _link_ends(link: UmlLink) -> list[_End]:
    found: list[_End] = []
    if link.target_role:
        found.append(_End(link.connector_id, link.source_id, link.target_id, link.target_role))
    if link.direction == BIDIRECTIONAL and link.source_role:
        found.append(_End(link.connector_id, link.target_id, link.source_id, link.source_role))
    return found


class _Pass:
    """The working state of one derivation: indexes of the inputs and the findings it collects."""

    def __init__(  # noqa: PLR0913 - the pass's inputs are PD-19's arguments, passed on as they are
        self,
        elements: list[UmlElement],
        compositions: list[UmlComposition],
        links: list[UmlLink],
        parent_of: Mapping[int, str],
        kinds: Mapping[int, str],
        left_out: Mapping[int, LeftOutReason],
        drawn_toolkit: Mapping[int, str],
        class_names: Mapping[int, str],
    ) -> None:
        self.element = {each.uml_class.object_id: each for each in elements}
        self.compositions = sorted(compositions, key=lambda each: each.composition_id)
        self.ends = _ends(links)
        self.kinds = kinds
        self.left_out = left_out
        self.toolkit = drawn_toolkit
        self.class_names = class_names
        self.problems: list[CheckProblem] = []
        self.lines: list[ReportLine] = []
        by_label = {each.label: key for key, each in self.element.items()}
        self.parent = {
            child: by_label[label] for child, label in parent_of.items() if label in by_label
        }
        self.inside: dict[
            int, int
        ] = {}  # a class left inside an own graph -> the class that is its whole
        self.live: list[UmlComposition] = []  # the compositions that convert to something

    def name(self, object_id: int) -> str:
        found = self.element.get(object_id)
        return found.label if found is not None else self.class_names.get(object_id, str(object_id))

    def problem(self, rule: UmlRule, element: str, message: str) -> None:
        self.problems.append(CheckProblem(rule=rule.value, element=element, message=message))

    def refuse(self, rule: UmlRule, each: UmlComposition, message: str) -> None:
        self.problem(rule, self.pair(each), message)

    def pair(self, each: UmlComposition) -> str:
        return f"{self.name(each.whole_id)} -> {self.name(each.part_id)}"

    def note(self, kind: ReportKind, element: str, message: str) -> None:
        self.lines.append(ReportLine(report_kind=kind, element=element, message=message))

    def not_generated(self, object_id: int) -> bool:
        """A class left out by a not-generated stereotype (a drawn toolkit class is not one)."""
        return (
            self.left_out.get(object_id) == LeftOutReason.NOT_GENERATED
            and object_id not in self.toolkit
        )

    def ancestors(self, object_id: int) -> list[int]:
        """The classes above one, nearest first; a loop of generalisations ends the walk."""
        found: list[int] = []
        current = self.parent.get(object_id)
        while current is not None and current not in found and current != object_id:
            found.append(current)
            current = self.parent.get(current)
        return found

    def descendants(self, object_id: int) -> list[int]:
        """The classes below one, sorted by name, each once."""
        return sorted(
            (key for key in self.element if object_id in self.ancestors(key)), key=self.name
        )

    def is_own_graph(self, each: UmlComposition) -> bool:
        return bool(each.own_graph) or (each.uml_stereotype or "").strip().lower() == OWN_GRAPH

    def mark_inside(self) -> None:
        """Leave the classes below a not-generated own-graph part inside it, then refuse a generalisation to one (A-7, A-8)."""
        self.fill_inside()
        self.refuse_inside_generalisations()
        for inner, whole in sorted(self.inside.items()):
            self.note(
                ReportKind.NOT_GENERATED,
                self.name(inner),
                f"inside the own graph of {self.name(whole)}",
            )

    def unmarked_parts_of(self, whole: int) -> list[int]:
        """The generated parts of a class that are not yet left inside."""
        return [
            each.part_id
            for each in self.compositions
            if each.whole_id == whole
            and each.part_id in self.element
            and each.part_id not in self.inside
        ]

    def fill_inside(self) -> None:
        """Mark every generated class below a not-generated own-graph part (A-8)."""
        queue = [
            each.part_id
            for each in self.compositions
            if self.is_own_graph(each) and self.not_generated(each.part_id)
        ]
        while queue:
            whole = queue.pop(0)
            for part in dict.fromkeys(self.unmarked_parts_of(whole)):
                self.inside[part] = whole
                queue.append(part)

    def refuse_inside_generalisations(self) -> None:
        """A generalisation to or from a class left inside is refused and dropped (A-7)."""
        for child, parent in sorted(self.parent.items()):
            for end in (child, parent):
                if end in self.inside:
                    self.problem(
                        UmlRule.BOUNDARY_OWNED,
                        self.name(end),
                        f"inside the own graph of {self.name(self.inside[end])}; "
                        "it cannot take part in a generalisation",
                    )
        self.parent = {
            child: parent
            for child, parent in self.parent.items()
            if child not in self.inside and parent not in self.inside
        }

    def exempt(self, each: UmlComposition) -> bool:
        """A composition whose whole is not generated or left inside converts to nothing (A-8)."""
        return self.not_generated(each.whole_id) or each.whole_id in self.inside

    def crossing(self, each: UmlComposition) -> bool:
        """Whether an end is no converted class: outside, excluded, a toolkit class or unknown (A-9)."""
        for end in (each.whole_id, each.part_id):
            if end in self.toolkit:
                self.refuse(
                    UmlRule.BOUNDARY_OWNED,
                    each,
                    "toolkit classes are composed by mixins, not compositions",
                )
                return True
            if end not in self.element and not self.not_generated(end):
                self.refuse(
                    UmlRule.BOUNDARY_OWNED, each, "the composition crosses the converted subtree"
                )
                return True
        return False

    def refused(self, each: UmlComposition) -> bool:
        """Every refusal of one composition that converts (PD-8, A-9, A-25); True when it is refused."""
        checks = (self.bad_stereotype, self.crossing, self.bad_part, self.cross_kind)
        return any(check(each) for check in checks)

    def bad_stereotype(self, each: UmlComposition) -> bool:
        stereotype = (each.uml_stereotype or "").strip()
        if not stereotype or self.is_own_graph(each):
            return False
        self.problem(
            UmlRule.NO_RULE, self.pair(each), f"connector stereotype {stereotype}: {NO_RULE_TAIL}"
        )
        return True

    def bad_part(self, each: UmlComposition) -> bool:
        """A part that is an enumeration or the tenant root, or whose storage disagrees with the stereotype (PD-8)."""
        part = self.element.get(each.part_id)
        own = self.is_own_graph(each)
        if part is None:
            message = None if own else "a not-generated part is stored apart: use «own graph»"
        elif part.is_enum:
            self.problem(
                UmlRule.NO_RULE, self.pair(each), f"composition to an enumeration: {NO_RULE_TAIL}"
            )
            return True
        elif part.is_tenant_root:
            self.problem(
                UmlRule.ROOT_CLASS, self.name(each.part_id), "the tenant root cannot be a part"
            )
            return True
        else:
            message = (
                "«own graph» to a generated class needs dependent-aggregates; mark the part "
                "with a not-generated stereotype or draw a plain composition"
                if own
                else None
            )
        if message is not None:
            self.refuse(UmlRule.BOUNDARY_OWNED, each, message)
        return message is not None

    def cross_kind(self, each: UmlComposition) -> bool:
        """A domain whole composing a part of another module kind is refused (A-25)."""
        whole, part = self.element.get(each.whole_id), self.element.get(each.part_id)
        if whole is None or part is None:
            return False
        whole_kind = self.kinds.get(whole.uml_class.package_id, DOMAIN)
        part_kind = self.kinds.get(part.uml_class.package_id, DOMAIN)
        if whole_kind != DOMAIN or part_kind == DOMAIN:
            return False
        self.refuse(
            UmlRule.BOUNDARY_OWNED,
            each,
            f"a domain part cannot live in module kind {part_kind} "
            f"(packages {'/'.join(whole.module_path or [])}, {'/'.join(part.module_path or [])})",
        )
        return True

    def screen(self) -> None:
        """Keep the compositions that convert: not exempt, not refused (Algorithm 2a, 2b)."""
        self.mark_inside()
        self.live = [
            each for each in self.compositions if not self.exempt(each) and not self.refused(each)
        ]

    def kind_of(self, object_id: int) -> str:
        return self.kinds.get(self.element[object_id].uml_class.package_id, DOMAIN)

    def part_ids(self) -> set[int]:
        return {each.part_id for each in self.live if each.part_id in self.element}

    def is_part(self, object_id: int) -> bool:
        """Whether a class is a composition's part, directly or by inheritance from any part (A-16)."""
        parts = self.part_ids()
        return object_id in parts or any(each in parts for each in self.ancestors(object_id))

    def applicable(self, object_id: int) -> list[UmlComposition]:
        """The compositions a class holds, its own and those of the classes above it."""
        held = {object_id, *self.ancestors(object_id)}
        return [
            each for each in self.live if each.whole_id in held and each.part_id in self.element
        ]

    def derived_roots(self) -> list[int]:
        """The concrete classes of domain modules that are no part, no enumeration, no tenant root (PD-5)."""
        return [
            key
            for key, each in sorted(self.element.items())
            if not (each.is_enum or each.is_abstract or each.is_tenant_root)
            and key not in self.inside
            and self.kind_of(key) == DOMAIN
            and not self.is_part(key)
        ]

    def tenant_root(self) -> int | None:
        found = [key for key, each in sorted(self.element.items()) if each.is_tenant_root]
        return found[0] if found else None

    def tops(self, roots: list[int]) -> list[int]:
        """The roots, the tenant root and the abstract classes whose concrete descendants are all tops."""
        tenant = self.tenant_root()
        concrete = set(roots) | ({tenant} if tenant is not None else set())
        abstract = {key for key in sorted(self.element) if self.is_abstract_top(key, concrete)}
        return sorted(concrete | abstract)

    def is_abstract_top(self, key: int, concrete: set[int]) -> bool:
        """An abstract class that is no part and whose concrete descendants are all tops."""
        each = self.element[key]
        if not each.is_abstract or each.is_enum or each.is_tenant_root or key in self.inside:
            return False
        below = self.concrete_below(key)
        return bool(below) and concrete.issuperset(below) and not self.is_part(key)

    def concrete_below(self, key: int) -> list[int]:
        """The concrete classes, no enumeration, that descend from a class."""
        return [
            other
            for other in self.descendants(key)
            if not (self.element[other].is_abstract or self.element[other].is_enum)
        ]

    def walk(self, top: int) -> list[int]:
        """The part classes an aggregate reaches from one top, depth first, each once; a recursion ends there."""
        seen: list[int] = []

        def enter(whole: int) -> None:
            for each in self.applicable(whole):
                for reached in [each.part_id, *self.descendants(each.part_id)]:
                    if reached not in seen:
                        seen.append(reached)
                        enter(reached)

        enter(top)
        return seen

    def successors(self, object_id: int) -> list[int]:
        return [
            reached
            for each in self.applicable(object_id)
            for reached in (each.part_id, *self.descendants(each.part_id))
        ]

    def cycle_through(self, start: int, allowed: set[int]) -> list[int] | None:
        """A path of compositions from a class back to itself through the classes no top reaches."""

        def go(node: int, path: list[int]) -> list[int] | None:
            for following in sorted(self.successors(node), key=self.name):
                if following == start:
                    return path
                if following in allowed and following not in path:
                    found = go(following, [*path, following])
                    if found is not None:
                        return found
            return None

        return go(start, [start])

    def check_reach(self, reach: Mapping[int, set[int]]) -> None:
        """Refuse each part class no top reaches: a cycle by its classes, any other by its wholes (A-1, A-2)."""
        lost = sorted(
            (k for k in self.element if self.is_part(k) and not reach.get(k)), key=self.name
        )
        reported: set[int] = set()
        for key in lost:
            if key in reported:
                continue
            cycle = self.cycle_through(key, set(lost))
            if cycle is not None:
                reported.update(cycle)
                path = f" {ARROW} ".join(self.name(each) for each in [*cycle, cycle[0]])
                message = f"compositions form a cycle {path} that no root reaches"
            else:
                held = {key, *self.ancestors(key)}
                wholes = sorted({self.name(e.whole_id) for e in self.live if e.part_id in held})
                message = f"no root reaches it (wholes {', '.join(wholes)})"
            self.problem(UmlRule.BOUNDARY_OWNED, self.name(key), message)

    def choose(self, each: UmlComposition, candidates: list[_End]) -> _End | None:
        """The association a composition marks (PD-2, D-6), or a problem and None."""
        pair = self.pair(each)
        if not candidates:
            message = f"a composition needs an association {pair} that names the role"
        elif each.role:
            named = [end for end in candidates if local_of(end.role) == local_of(each.role)]
            if named:
                return named[0]
            message = f"role {each.role} names no association {pair}"
        elif len(candidates) == 1:
            return candidates[0]
        else:
            roles = ", ".join(sorted(end.role for end in candidates))
            message = (
                f"two associations ({roles}) beside one composition; name one on the composition"
            )
        self.problem(UmlRule.BOUNDARY_OWNED, pair, message)
        return None

    def owned_ends(self) -> list[UmlOwnedEnd]:
        """The ends the compositions mark; an own-graph composition marks one too, which is not owned (PD-9)."""
        found: list[UmlOwnedEnd] = []
        for each in self.live:
            candidates = [
                end
                for end in self.ends
                if end.holder_id == each.whole_id and end.other_id == each.part_id
            ]
            chosen = self.choose(each, candidates)
            if chosen is not None and not self.is_own_graph(each):
                found.append(UmlOwnedEnd(link_id=chosen.link_id, holder_id=each.whole_id))
        return sorted(found, key=lambda end: end.link_id)

    def compare_drawn(self, roots: list[int]) -> None:
        """DEC-6: the drawn «root» classes of domain modules against the derived ones (PD-6, A-12)."""
        drawn = self.drawn_roots()
        if not drawn:
            return
        before = len(self.problems)
        concrete = {key for key in drawn if not self.element[key].is_abstract}
        for key in sorted(set(drawn) - concrete):
            self.problem(
                UmlRule.ROOT_CLASS,
                self.name(key),
                "abstract «root»: drop it, the abstract-root rule derives it",
            )
        self.refuse_disagreeing(concrete, set(roots))
        if len(self.problems) == before:
            self.note(
                ReportKind.DEPRECATED_ROOT,
                "model",
                f"{len(roots)} «root» stereotypes agree with the derived roots; drop them",
            )

    def drawn_roots(self) -> list[int]:
        """The classes of domain modules the model draws «root», left-inside ones, enumerations and the tenant root aside."""
        return [
            key
            for key, each in sorted(self.element.items())
            if each.is_drawn_root
            and not (each.is_enum or each.is_tenant_root)
            and key not in self.inside
            and self.kind_of(key) == DOMAIN
        ]

    def wholes_of(self, key: int) -> str:
        """The names of the wholes a class is a part of, directly or by inheritance, joined."""
        held = {key, *self.ancestors(key)}
        return ", ".join(sorted({self.name(e.whole_id) for e in self.live if e.part_id in held}))

    def refuse_disagreeing(self, drawn: set[int], derived: set[int]) -> None:
        """A problem for each class drawn «root» and not derived, and each derived and not drawn (PD-6)."""
        for key in sorted(drawn - derived, key=self.name):
            wholes = self.wholes_of(key)
            why = f"a part of {wholes}" if wholes else "not a derived root"
            self.problem(UmlRule.ROOT_CLASS, self.name(key), f"drawn «root» but {why}")
        for key in sorted(derived - drawn, key=self.name):
            self.problem(
                UmlRule.ROOT_CLASS,
                self.name(key),
                "a root (no composition's part) but not drawn «root»",
            )

    def root_lines(self, roots: list[int]) -> None:
        """One ``root`` line for each derived root, and for the tenant root when it has parts (PD-5)."""
        tenant = self.tenant_root()
        for top in [*roots, *([tenant] if tenant is not None else [])]:
            parts = [self.name(each) for each in self.walk(top)]
            if parts or top != tenant:
                self.note(
                    ReportKind.ROOT,
                    self.name(top),
                    f"parts {', '.join(parts)}" if parts else "no parts",
                )

    def result(self) -> UmlAggregates:
        self.screen()
        roots = self.derived_roots()
        tops = self.tops(roots)
        reach: dict[int, set[int]] = {}
        for top in tops:
            for part in self.walk(top):
                reach.setdefault(part, set()).add(top)
        self.check_reach(reach)
        owned = self.owned_ends()
        self.compare_drawn(roots)
        self.root_lines(roots)
        return UmlAggregates(
            root_ids=roots,
            tenant_root_id=self.tenant_root(),
            part_of=[
                UmlPartOf(
                    part_id=each.part_id,
                    whole_id=each.whole_id,
                    own_graph=self.is_own_graph(each),
                    composition_id=each.composition_id,
                )
                for each in self.live
            ],
            reached_from=[
                UmlReach(part_id=part, top_ids=sorted(found))
                for part, found in sorted(reach.items())
            ],
            owned_ends=owned,
            left_inside_ids=sorted(self.inside),
            problems=sorted(self.problems, key=lambda each: (each.element or "", each.message)),
            report_lines=sorted(
                self.lines,
                key=lambda each: (ReportKind(each.report_kind).value, each.element, each.message),
            ),
        )


def derive_aggregates(  # noqa: PLR0913 - PD-19's six inputs and the two a message needs, no Context
    elements: list[UmlElement],
    compositions: list[UmlComposition],
    links: list[UmlLink],
    parent_of: Mapping[int, str],
    package_kinds: Mapping[int, str],
    left_out: Mapping[int, LeftOutReason],
    drawn_toolkit: Mapping[int, str],
    class_names: Mapping[int, str],
) -> UmlAggregates:
    """The tree, the derived roots and the owned ends of the compositions of a model (PD-4, PD-5, PD-19).

    Args:
        elements: The classes and enumerations the conversion generates.
        compositions: The compositions the reader found, each read once.
        links: The connectors; the associations beside the compositions are found among them (PD-2).
        parent_of: The label of the parent of each class that has one.
        package_kinds: The ``module_kind`` of each package (``package_kinds``).
        left_out: The classes the conversion leaves out, and why.
        drawn_toolkit: The left-out classes that are the toolkit's, by id.
        class_names: The names of the classes that are no element, for a message.

    Returns:
        The roots, the tree rows, the tops that reach each part, the owned ends, the classes left
        inside an own graph, and the problems and report lines found.
    """
    return _Pass(
        elements,
        compositions,
        links,
        parent_of,
        package_kinds,
        left_out,
        drawn_toolkit,
        class_names,
    ).result()
