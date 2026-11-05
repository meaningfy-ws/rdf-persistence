"""The one place that turns values into SPARQL text (PD-3).

``term`` renders an rdflib IRI, literal or blank node as an escaped SPARQL term. ``fill`` puts
rendered terms into a query template whose placeholders are ``$name``. No other code produces
SPARQL text from a value, so injection is audited here only.
"""

import re
from string import Template

from rdflib import BNode, Literal, URIRef

_FORBIDDEN_IRI_CHARS = re.compile(r'[\x00-\x20<>"{}|\\^`\x7f]')
_BLANK_LABEL = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
_LANGUAGE_TAG = re.compile(r"[A-Za-z]+(-[A-Za-z0-9]+)*")
_STRING_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class SparqlError(ValueError):
    """A value cannot become a SPARQL term, or a template and its terms do not match."""


class SparqlTerm(str):
    """SPARQL text that ``term`` produced: the only kind of value ``fill`` accepts."""

    __slots__ = ()


def _iri(value: str) -> str:
    if not value or _FORBIDDEN_IRI_CHARS.search(value):
        raise SparqlError(f"not a valid IRI for SPARQL: {value!r}")
    return f"<{value}>"


def _string(value: str) -> str:
    escaped = "".join(_STRING_ESCAPES.get(c, c) for c in value)
    return '"' + _CONTROL.sub(lambda m: f"\\u{ord(m.group()):04x}", escaped) + '"'


def _literal(value: Literal) -> str:
    text = _string(str(value))
    if value.language:
        if not _LANGUAGE_TAG.fullmatch(value.language):
            raise SparqlError(f"not a valid language tag: {value.language!r}")
        return f"{text}@{value.language}"
    if value.datatype:
        return f"{text}^^{_iri(str(value.datatype))}"
    return text


def term(value: URIRef | Literal | BNode) -> SparqlTerm:
    """Render an IRI, literal or blank node as an escaped SPARQL term.

    Raises:
        SparqlError: The value is a raw string, or an IRI, language tag or blank-node label that
            could change the meaning of the text around it.
    """
    if isinstance(value, URIRef):
        return SparqlTerm(_iri(str(value)))
    if isinstance(value, Literal):
        return SparqlTerm(_literal(value))
    if isinstance(value, BNode):
        if not _BLANK_LABEL.fullmatch(str(value)):
            raise SparqlError(f"not a valid blank node label: {str(value)!r}")
        return SparqlTerm(f"_:{value}")
    raise SparqlError(
        f"term() takes an rdflib URIRef, Literal or BNode, not {type(value).__name__}"
    )


def fill(template: str, **terms: SparqlTerm) -> str:
    """Substitute each ``$name`` placeholder of ``template`` with its rendered term.

    Raises:
        SparqlError: A value is not a ``SparqlTerm``, or the names do not match the placeholders.
    """
    raw = sorted(name for name, value in terms.items() if not isinstance(value, SparqlTerm))
    if raw:
        raise SparqlError(f"fill() takes only values from term(); raw value for {raw}")
    placeholders = set(Template(template).get_identifiers())
    if missing := placeholders - terms.keys():
        raise SparqlError(f"missing terms for {sorted(missing)}")
    if unused := terms.keys() - placeholders:
        raise SparqlError(f"unused terms {sorted(unused)}")
    return Template(template).substitute(terms)
