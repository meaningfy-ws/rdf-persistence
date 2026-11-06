"""The one place that turns values into SPARQL text (PD-3).

``term`` renders an rdflib IRI, literal or blank node as an escaped SPARQL term. ``fill`` puts
rendered terms into a query template whose placeholders are ``$name``. No other code produces
SPARQL text from a value, so injection is audited here only.
"""

import re
from collections.abc import Iterable
from string import Template

from rdflib import BNode, Literal, URIRef

from rdf_persistence.domain.exceptions import SparqlError

_FORBIDDEN_IRI_CHARS = re.compile(r'[\x00-\x20<>"{}|\\^`\x7f]')
_BLANK_LABEL = re.compile(r"[A-Za-z0-9_]([A-Za-z0-9_.-]*[A-Za-z0-9_-])?")  # may not end in "."
_LANGUAGE_TAG = re.compile(r"[A-Za-z]+(-[A-Za-z0-9]+)*")
_STRING_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


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


Triple = tuple[URIRef | BNode, URIRef, URIRef | Literal | BNode]


def triples_block(triples: Iterable[Triple]) -> SparqlTerm:
    """Render triples as the dotted triple patterns of an ``INSERT DATA`` or template body."""
    return SparqlTerm(" ".join(f"{term(s)} {term(p)} {term(o)} ." for s, p, o in triples))


def term_list(values: Iterable[URIRef | Literal | BNode]) -> SparqlTerm:
    """Render values as the comma-separated terms of an ``IN (...)`` list."""
    return SparqlTerm(", ".join(term(value) for value in values))


_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def match_patterns(variable: str, pairs: Iterable[tuple[URIRef, URIRef | Literal]]) -> SparqlTerm:
    """Render ``?variable <predicate> <value> .`` for each pair: equality filters on a subject variable."""
    if not _VARIABLE.fullmatch(variable):
        raise SparqlError(f"not a plain variable name: {variable!r}")
    return SparqlTerm(" ".join(f"?{variable} {term(p)} {term(o)} ." for p, o in pairs))


def count(value: int) -> SparqlTerm:
    """Render a non-negative integer as the digits of a ``LIMIT`` or ``OFFSET``."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SparqlError(f"a count is a non-negative integer, not {value!r}")
    return SparqlTerm(str(value))


def order_by(*keys: tuple[str, bool]) -> SparqlTerm:
    """Render the sort keys, each a ``(variable, descending)`` pair, as the conditions of an ``ORDER BY``."""
    for variable, _ in keys:
        if not _VARIABLE.fullmatch(variable):
            raise SparqlError(f"not a plain variable name: {variable!r}")
    return SparqlTerm(" ".join(f"{'DESC' if down else 'ASC'}(?{name})" for name, down in keys))
