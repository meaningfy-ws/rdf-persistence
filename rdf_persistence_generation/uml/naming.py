"""Names, IRIs, titles, permissible-value keys and root paths of the UML conversion (PD-6, PD-10, PD-12).

Pure functions: the prefix maps are plain arguments, nothing is read or written here.
"""

import re
from collections.abc import Mapping

from linkml_runtime.utils.metamodelcore import URIorCURIE

from rdf_persistence_generation.generated.rp_generation import CheckProblem, UmlName, UmlRule

CLASS_NAME_PATTERN = "[A-Z][a-zA-Z0-9]+"
SLOT_NAME_PATTERN = "[a-z][_a-z0-9]+"
CURIE_SEPARATOR = ":"
PROBE_PREFIX = "pfx"

_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+[0-9]*")
_VOWELS = "aeiou"
_ES_ENDINGS = ("s", "x", "z", "ch", "sh")


def local_of(written: str) -> str:
    """The local name of a written ``pfx:Local`` name, how an element is named in a problem or a report line."""
    return written.rsplit(CURIE_SEPARATOR, 1)[-1]


def _words(local: str) -> list[str]:
    return _WORD.findall(local)


def slot_name(written: str) -> str:
    """The local name in snake case: ``hasChapter`` -> ``has_chapter``, ``ISBNRecord`` -> ``isbn_record``."""
    return "_".join(word.lower() for word in _words(local_of(written)))


def permissible_value_key(literal: str) -> str:
    """The key of an enumeration literal: its local name in snake case (``lib:onLoan`` -> ``on_loan``)."""
    return slot_name(literal)


def title_for(local: str, alias: str | None = None) -> str:
    """The alias when set, else the name split into words: first capitalised, the rest lower-cased unless all capitals."""
    if alias:
        return alias
    words = [word if word.isupper() else word.lower() for word in _words(local)]
    if words and not words[0].isupper():
        words[0] = words[0].capitalize()
    return " ".join(words)


def rp_path_for(class_name: str) -> str:
    """The plural of the class name in kebab case: ``Library`` -> ``libraries``, ``Box`` -> ``boxes``."""
    singular = "-".join(word.lower() for word in _words(class_name))
    if singular.endswith("y") and len(singular) > 1 and singular[-2] not in _VOWELS:
        return singular[:-1] + "ies"
    if singular.endswith(_ES_ENDINGS):
        return singular + "es"
    return singular + "s"


def check_class_name(name: str, element: str) -> CheckProblem | None:
    """A problem when a class or enum name breaks the lint pattern (F-7), else None."""
    if re.fullmatch(CLASS_NAME_PATTERN, name):
        return None
    return CheckProblem(
        rule=UmlRule.CLASS_IRI.value,
        element=element,
        message=f"name {name} does not match {CLASS_NAME_PATTERN}",
    )


def check_slot_name(name: str, element: str) -> CheckProblem | None:
    """A problem when a slot name or permissible-value key breaks the lint pattern (F-7), else None."""
    if re.fullmatch(SLOT_NAME_PATTERN, name):
        return None
    return CheckProblem(
        rule=UmlRule.ATTRIBUTE_SLOT.value,
        element=element,
        message=f"name {name} does not match {SLOT_NAME_PATTERN}",
    )


def check_local_name(local: str, element: str, rule: UmlRule) -> CheckProblem | None:
    """A problem when a written local name cannot be the local part of a CURIE linkml accepts (D-29 C-1).

    The test is the one ``linkml_runtime`` applies to a ``slot_uri`` or a ``meaning``, so a name that
    passes here never reaches a ``ValueError`` when the definition is built.
    """
    if URIorCURIE.is_valid(f"{PROBE_PREFIX}{CURIE_SEPARATOR}{local}"):
        return None
    return CheckProblem(
        rule=rule.value, element=element, message=f"'{local}' is not a valid local name"
    )


def resolve_name(
    written: str,
    element: str,
    prefixes: Mapping[str, str],
    metamodel_prefixes: Mapping[str, str],
    prefixes_file: str,
) -> UmlName | CheckProblem:
    """Split ``pfx:Local`` and expand it with the file's prefixes; an unknown prefix is a problem (PD-6).

    The output CURIE takes the metamodel's prefix name when the metamodel names the namespace, else the
    file's. An unprefixed name has no explicit IRI.
    """
    if CURIE_SEPARATOR not in written:
        return UmlName(name=written)
    prefix, local = written.split(CURIE_SEPARATOR, 1)
    if prefix not in prefixes:
        return CheckProblem(
            rule=UmlRule.CLASS_IRI.value,
            element=element,
            message=f"prefix {prefix} is not in {prefixes_file}",
        )
    namespace = prefixes[prefix]
    by_namespace = {ns: name for name, ns in metamodel_prefixes.items()}
    return UmlName(
        name=local, iri=namespace + local, curie=f"{by_namespace.get(namespace, prefix)}:{local}"
    )
