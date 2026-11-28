"""What one conversion shares between its passes: the findings it collects and the elements it has classified.

What is here is working state of one run (the findings and the indexes the passes read), plain classes because
the model guard refuses a hand-written dataclass. The records of the model (``UmlElement``, ``UmlPackagePath``)
are generated; their helpers are functions here.
"""

from collections.abc import Mapping
from typing import Final

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    LeftOutReason,
    ReportKind,
    ReportLine,
    UmlElement,
    UmlName,
    UmlPackagePath,
    UmlRule,
    UmlSettings,
)
from rdf_persistence_generation.problems import format_problem
from rdf_persistence_generation.uml.naming import CURIE_SEPARATOR, resolve_name
from rdf_persistence_generation.uml.toolkit import Toolkit

PREFIXES_FILE: Final = "the prefixes file"
NO_RULE_TAIL: Final = "no rule converts it"
TOOLKIT_PREFIX: Final = "rp"  # the metamodel's name for the toolkit's own namespace


def local_of(written: str) -> str:
    """The local name of a written ``pfx:Local`` name, how an element is named in a problem or a report line."""
    return written.rsplit(CURIE_SEPARATOR, 1)[-1]


class Findings:
    """The problems and report lines of a run, each kept once and handed back sorted (PD-22)."""

    def __init__(self) -> None:
        self._problems: dict[str, CheckProblem] = {}
        self._report: dict[tuple[str, str, str], ReportLine] = {}

    def problem(self, rule: UmlRule, element: str, message: str) -> None:
        found = CheckProblem(rule=rule.value, element=element, message=message)
        self._problems[format_problem(found)] = found

    def add(self, found: CheckProblem) -> None:
        self._problems[format_problem(found)] = found

    def no_rule(self, element: str, what: str) -> None:
        """An element no rule maps: ``[no_rule] <element>: <what>: no rule converts it``."""
        self.problem(UmlRule.NO_RULE, element, f"{what}: {NO_RULE_TAIL}")

    def note(self, kind: ReportKind, element: str, message: str) -> None:
        self._report[(kind.value, element, message)] = ReportLine(
            report_kind=kind, element=element, message=message
        )

    def problems(self) -> list[CheckProblem]:
        return [self._problems[text] for text in sorted(self._problems)]

    def report(self) -> list[ReportLine]:
        return [self._report[key] for key in sorted(self._report)]


def path_of(element: UmlElement) -> tuple[str, ...]:
    """The packages an element sits in below the subtree package, as a key."""
    return tuple(element.module_path or ())


def below_of(path: UmlPackagePath) -> tuple[str, ...]:
    """The packages between the subtree package and a package, as a key."""
    return tuple(path.below or ())


def is_boundary_root(element: UmlElement) -> bool:
    """Whether the class is the top of an aggregate: a root (derived, PD-5) or the tenant root."""
    return bool(element.is_root or element.is_tenant_root)


def literals_of(element: UmlElement) -> int:
    """How many literals an enumeration lists; a class has its attributes in their place."""
    return len(element.uml_class.uml_attributes or [])


class Context:
    """The inputs of a run with the indexes the passes read."""

    def __init__(
        self,
        settings: UmlSettings,
        toolkit: Toolkit,
        prefixes: dict[str, str],
    ) -> None:
        self.settings = settings
        self.toolkit = toolkit
        self.metamodel_prefixes: Mapping[str, str] = toolkit.prefixes()
        self.prefixes = prefixes
        self.findings = Findings()
        self.elements: dict[int, UmlElement] = {}
        self.left_out: dict[int, LeftOutReason] = {}
        self.left_out_enums: set[int] = (
            set()
        )  # left out as not generated, and an enumeration (R-30)
        self.class_names: dict[
            int, str
        ] = {}  # every class the model lists, converted or not (D-17)
        self.paths: dict[int, UmlPackagePath] = {}
        self.tags: dict[int, dict[str, str]] = {}
        self.tag_values: dict[
            int, dict[str, list[str]]
        ] = {}  # every value of a tag, for the ones a class may repeat (R-21)
        self.slot_aliases: dict[
            int, dict[str, str]
        ] = {}  # a class's slot names by every name written for them (PD-21)
        self.unknown_prefixes: set[str] = set()
        self.drawn_toolkit: dict[
            int, str
        ] = {}  # drawn classes that are toolkit classes: id -> name (R-28)
        self.drawn_parents: dict[
            int, list[str]
        ] = {}  # a class's drawn toolkit parents, connector order

    def not_generated_enum(self, object_id: int | None) -> bool:
        """Whether the element is an enumeration the run leaves out as not generated (R-30)."""
        return object_id in self.left_out_enums

    def toolkit_name(self, written: str) -> str | None:
        """The toolkit class a drawn class stands for: its IRI is a toolkit ``class_uri``, or it is the toolkit's
        namespace with a toolkit class's name (PD-17); None when it is neither or its prefix is unknown."""
        resolved = resolve_name(
            written, written, self.prefixes, self.metamodel_prefixes, PREFIXES_FILE
        )
        if not isinstance(resolved, UmlName) or resolved.iri is None:
            return None
        by_uri = self.toolkit.class_by_uri(resolved.iri)
        if by_uri is not None:
            return str(by_uri.name)
        in_toolkit_namespace = (
            resolved.iri == self.metamodel_prefixes.get(TOOLKIT_PREFIX, "") + resolved.name
        )
        return (
            resolved.name
            if in_toolkit_namespace and self.toolkit.class_by_name(resolved.name)
            else None
        )

    def resolve(self, written: str, element: str) -> UmlName | None:
        """Expand a written name; an unknown prefix is one problem for the prefix, naming the first element."""
        resolved = resolve_name(
            written, element, self.prefixes, self.metamodel_prefixes, PREFIXES_FILE
        )
        if isinstance(resolved, UmlName):
            return resolved
        prefix = written.split(CURIE_SEPARATOR, 1)[0]
        if prefix not in self.unknown_prefixes:
            self.unknown_prefixes.add(prefix)
            self.findings.add(resolved)
        return None

    def default_namespace(self) -> str:
        return self.prefixes.get(self.settings.default_prefix, "")

    def namespace_of(self, curie_prefix: str) -> str:
        """The namespace a prefix of the output stands for: the metamodel's name first, else the file's."""
        return self.metamodel_prefixes.get(curie_prefix) or self.prefixes.get(curie_prefix, "")

    def used_prefix(self, curie: str | None) -> tuple[str, str] | None:
        """The prefix a CURIE uses and its namespace, for the module's ``prefixes``."""
        if not curie or CURIE_SEPARATOR not in curie:
            return None
        prefix = curie.split(CURIE_SEPARATOR, 1)[0]
        return prefix, self.namespace_of(prefix)
