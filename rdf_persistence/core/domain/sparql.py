"""The one place that turns values into SPARQL text (PD-3).

``term`` renders an rdflib IRI, literal or blank node as an escaped SPARQL term. ``fill`` puts
rendered terms into a query template whose placeholders are ``$name``. No other code produces
SPARQL text from a value, so injection is audited here only.
"""

import re
from collections.abc import Collection, Iterable, Iterator, Sequence
from string import Template
from typing import Any

from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema
from pyparsing import ParseBaseException, ParseResults
from rdflib import RDF, BNode, Literal, URIRef, Variable

from rdf_persistence.core.domain.exceptions import SparqlError
from rdf_persistence.core.domain.sparql_parsing import CompValue, parse_query, parse_update

FORBIDDEN_IRI_CHARS = re.compile(r'[\x00-\x20<>"{}|\\^`\x7f]')
_ABSOLUTE_IRI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:.+")  # a scheme, then something
_BLANK_LABEL = re.compile(r"[A-Za-z0-9_]([A-Za-z0-9_.-]*[A-Za-z0-9_-])?")  # may not end in "."
_LANGUAGE_TAG = re.compile(r"[A-Za-z]+(-[A-Za-z0-9]+)*")
_STRING_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# Before the control escapes, a backslash in escaped text is only ever the second of "\\".
_AFTER_BACKSLASH = re.compile(r"(?<=\\)[uU]")


class SparqlTerm(str):
    """SPARQL text that ``term`` produced: the only kind of value ``fill`` accepts."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """A model field of this type takes a ``SparqlTerm`` and nothing else: a raw ``str`` fails."""
        return core_schema.is_instance_schema(cls)


def is_absolute_iri(value: str) -> bool:
    """Whether ``value`` is an absolute IRI (a scheme, then more) holding none of ``FORBIDDEN_IRI_CHARS``."""
    return bool(_ABSOLUTE_IRI.fullmatch(value)) and not FORBIDDEN_IRI_CHARS.search(value)


def _iri(value: str) -> str:
    if not value or FORBIDDEN_IRI_CHARS.search(value):
        raise SparqlError(f"not a valid IRI for SPARQL: {value!r}")
    return f"<{value}>"


def _codepoint_escape(match: re.Match[str]) -> str:
    # The 8-digit form (#270): rdflib reads \u with 4 or 8 digits, so "\u001f" + "0000" would
    # extend to one code point; nothing can extend an escape that already has 8.
    return f"\\U{ord(match.group()):08X}"


def _string(value: str) -> str:
    escaped = "".join(_STRING_ESCAPES.get(c, c) for c in value)
    # SPARQL expands \u and \U over the whole request first (#108); the u after an escaped
    # backslash goes out as a codepoint escape, so both readings give the text back.
    escaped = _AFTER_BACKSLASH.sub(_codepoint_escape, escaped)
    return '"' + _CONTROL.sub(_codepoint_escape, escaped) + '"'


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


def fragment(template: str, **terms: SparqlTerm) -> SparqlTerm:
    """``fill`` for a piece of a larger text: the result is a ``SparqlTerm``, so ``join`` and ``fill`` take it."""
    return SparqlTerm(fill(template, **terms))


def _bundle_terms(terms: BaseModel, more: dict[str, SparqlTerm]) -> dict[str, SparqlTerm]:
    """The set fields of a term model, with ``more``; a ``None`` field is left out.

    Iterating the model yields its attribute values as they are, so each stays a ``SparqlTerm``
    (``model_dump()`` would turn it into a ``str``).
    """
    given = {name: value for name, value in terms if value is not None}
    if twice := sorted(given.keys() & more.keys()):
        raise SparqlError(f"term given twice: {twice}")
    return {**given, **more}


def fill_terms(template: str, terms: BaseModel, **more: SparqlTerm) -> str:
    """``fill`` with the ``SparqlTerm`` fields of a model, and ``more`` that one call adds to it.

    Raises:
        SparqlError: A name is both a field of ``terms`` and in ``more``, or ``fill`` refuses.
    """
    return fill(template, **_bundle_terms(terms, more))


def fragment_terms(template: str, terms: BaseModel, **more: SparqlTerm) -> SparqlTerm:
    """``fill_terms`` for a piece of a larger text: the result is a ``SparqlTerm``."""
    return SparqlTerm(fill_terms(template, terms, **more))


def _joined(separator: str, parts: Iterable[SparqlTerm], caller: str) -> SparqlTerm:
    items = list(parts)
    if raw := [type(p).__name__ for p in items if not isinstance(p, SparqlTerm)]:
        raise SparqlError(f"{caller}() takes only SparqlTerm parts; got {raw}")
    return SparqlTerm(separator.join(items))


def join(parts: Iterable[SparqlTerm]) -> SparqlTerm:
    """Join ``SparqlTerm``s, one space apart, into one: patterns, guards or a ``VALUES`` list.

    Raises:
        SparqlError: A part is not a ``SparqlTerm``.
    """
    return _joined(" ", parts, "join")


def union(parts: Iterable[SparqlTerm]) -> SparqlTerm:
    """Join ``SparqlTerm``s, each a group pattern, into the alternatives of one ``UNION``.

    Raises:
        SparqlError: A part is not a ``SparqlTerm``.
    """
    return _joined(" UNION ", parts, "union")


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


def contains_patterns(variable: str, pairs: Iterable[tuple[URIRef, Literal]]) -> SparqlTerm:
    """Render a case-insensitive substring filter on ``?variable`` for each ``(predicate, text)`` pair.

    The n-th pair (from 0) becomes ``FILTER EXISTS { ?variable <predicate> ?variable_cN . FILTER
    (CONTAINS(LCASE(STR(?variable_cN)), LCASE("text"))) }``: a subject matches when some value of the
    predicate holds the text. Each pair has its own ``?variable_cN``, so the filters never share a
    binding. The predicate and the text go through ``term``, like the value of ``match_patterns``;
    no pairs render the empty pattern.

    Raises:
        SparqlError: The variable is not a plain name, or a text is a raw string, not a ``Literal``.
    """
    if not _VARIABLE.fullmatch(variable):
        raise SparqlError(f"not a plain variable name: {variable!r}")
    filters = []
    for n, (predicate, text) in enumerate(pairs):
        if not isinstance(text, Literal):
            raise SparqlError(
                f"contains_patterns() takes a Literal text, not {type(text).__name__}"
            )
        bound = f"?{variable}_c{n}"
        filters.append(
            f"FILTER EXISTS {{ ?{variable} {term(predicate)} {bound} . "
            f"FILTER (CONTAINS(LCASE(STR({bound})), LCASE({term(text)}))) }}"
        )
    return SparqlTerm(" ".join(filters))


def hop_patterns(  # noqa: PLR0913 - the hop's two ends, its graph suffix, the hidden graphs and the inner patterns (D-2)
    subject: str,
    predicate: URIRef,
    target: str,
    suffix: str,
    hidden: Sequence[URIRef],
    inner: SparqlTerm,
) -> SparqlTerm:
    """Render one reference hop from ``?subject`` to ``?target``, with ``inner`` holding in the target's graph.

    ``?subject <predicate> ?target .`` binds ``?target_g`` to the target's IRI plus ``suffix`` (the
    aggregate's graph, which the caller knows and ``core`` does not), leaves out each ``hidden`` graph
    with a ``NOT IN`` filter (none when ``hidden`` is empty) and puts ``inner`` in ``GRAPH ?target_g``.
    The suffix goes through ``term`` as a literal, the predicate and each hidden graph as IRIs.

    Raises:
        SparqlError: A variable is not a plain name, or an IRI is not a safe one.
    """
    for variable in (subject, target):
        if not _VARIABLE.fullmatch(variable):
            raise SparqlError(f"not a plain variable name: {variable!r}")
    if not isinstance(inner, SparqlTerm):
        raise SparqlError(f"hop_patterns() takes a SparqlTerm inner, not {type(inner).__name__}")
    bound = f"?{target}_g"
    parts = [
        f"?{subject} {term(predicate)} ?{target} .",
        f"BIND (IRI(CONCAT(STR(?{target}), {term(Literal(suffix))})) AS {bound})",
    ]
    if hidden:
        parts.append(f"FILTER ({bound} NOT IN ({term_list(hidden)}))")
    parts.append(f"GRAPH {bound} {{ {inner} }}")
    return SparqlTerm(" ".join(parts))


def no_value_patterns(variable: str, predicates: Iterable[URIRef]) -> SparqlTerm:
    """Render ``FILTER NOT EXISTS { ?variable <predicate> ?variable_aN . }`` for the n-th predicate (from 0).

    A subject matches when it holds no statement of the predicate at all (D-9): a blank node is a value,
    unlike in ``absent_patterns``, which a unique key reads. Each predicate has its own
    ``?variable_aN``; no predicates render the empty pattern.

    Raises:
        SparqlError: The variable is not a plain name, or a predicate is not a safe IRI.
    """
    if not _VARIABLE.fullmatch(variable):
        raise SparqlError(f"not a plain variable name: {variable!r}")
    return SparqlTerm(
        " ".join(
            f"FILTER NOT EXISTS {{ ?{variable} {term(p)} ?{variable}_a{n} . }}"
            for n, p in enumerate(predicates)
        )
    )


def value_patterns(subject: str, predicates: Sequence[URIRef]) -> SparqlTerm:
    """Render ``?subject <predicate> ?v0 .``, ``?v1`` and so on, one pattern per predicate in order."""
    if not _VARIABLE.fullmatch(subject):
        raise SparqlError(f"not a plain variable name: {subject!r}")
    return SparqlTerm(" ".join(f"?{subject} {term(p)} ?v{n} ." for n, p in enumerate(predicates)))


def absent_patterns(subject: str, predicates: Sequence[URIRef]) -> SparqlTerm:
    """Render ``FILTER NOT EXISTS { ?subject <predicate> ?key_absent_0 . FILTER (!isBlank(…)) }`` per predicate.

    A blank node is no value, so a predicate holding only blank nodes counts as absent (PD-3).
    """
    if not _VARIABLE.fullmatch(subject):
        raise SparqlError(f"not a plain variable name: {subject!r}")
    return SparqlTerm(
        " ".join(
            f"FILTER NOT EXISTS {{ ?{subject} {term(p)} ?key_absent_{n} . "
            f"FILTER (!isBlank(?key_absent_{n})) }}"
            for n, p in enumerate(predicates)
        )
    )


def optional_value_patterns(
    subject: str, predicates: Sequence[URIRef], default: URIRef
) -> SparqlTerm:
    """Render, per predicate, an ``OPTIONAL`` value bound to ``?v0``, ``?v1`` … or ``default`` when it is absent.

    The variables are those of ``value_variables``; a blank node is no value (PD-5).
    """
    if not _VARIABLE.fullmatch(subject):
        raise SparqlError(f"not a plain variable name: {subject!r}")
    return SparqlTerm(
        " ".join(
            f"OPTIONAL {{ ?{subject} {term(p)} ?key_raw_{n} . FILTER (!isBlank(?key_raw_{n})) }} "
            f"BIND (COALESCE(?key_raw_{n}, {term(default)}) AS ?v{n})"
            for n, p in enumerate(predicates)
        )
    )


def value_variables(number: int) -> SparqlTerm:
    """Render the variables ``?v0 ?v1 …`` that ``value_patterns`` binds, ``number`` of them."""
    # count() refuses a bool, a negative or a non-int
    return SparqlTerm(" ".join(f"?v{n}" for n in range(int(count(number)))))


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


# -- the one check of untrusted pattern text (PD-6, PD-21, PD-22) -----------------------------------

# SPARQL expands \uXXXX and \UXXXXXXXX before it reads a word, so the tree could differ from the text.
CODEPOINT_ESCAPE = re.compile(r"\\[uU]")
_GRAPH_VARIABLE = "rp_graph"
_RESERVED_PREFIX = "rp_"
# The parse-tree nodes, as rdflib's parser names them: a graph pattern, a service pattern, and the
# GRAPH block of a template.
_GRAPH_NODES = frozenset({"GraphGraphPattern", "ServiceGraphPattern", "QuadsNotTriples"})
_PREFIXED_NAME = "pname"
_TOO_LONG = (
    "is too long to check; split the step into smaller steps"  # rdflib gives up at ~100 triples
)


def checked_group(text: str, *, template: bool, forbidden: Collection[URIRef] = ()) -> SparqlTerm:
    """``text`` as a group graph pattern of a migration step, once the parser has read it alone.

    ``template`` is False for a where pattern (read as ``ASK { text }``) and True for a delete or
    insert pattern (read as ``INSERT { text } WHERE {}``). The checks read the parse tree, not the
    text: no GRAPH or SERVICE, no variable starting ``rp_`` but ``?rp_graph``, no prefixed name,
    no codepoint escape; in a template also no blank node or collection and no IRI of ``forbidden``
    (the predicates the toolkit keeps for itself, which the caller names: a layer above knows them).

    Raises:
        SparqlError: The text breaks one check; the message says which, without naming the pattern.
    """
    if CODEPOINT_ESCAPE.search(text):
        raise SparqlError("has a codepoint escape (\\u or \\U); write the character itself")
    tree = _parsed(text, template)
    try:
        problems = (_node_problem(node, template, forbidden) for node in _nodes(tree))
        problem = next(filter(None, problems), None)
    except RecursionError as error:
        raise SparqlError(_TOO_LONG) from error
    if problem:
        raise SparqlError(problem)
    return SparqlTerm(text)


def _parsed(text: str, template: bool) -> object:
    """What rdflib's parser reads from ``text`` alone; names are not yet resolved against a prefix."""
    try:
        if template:
            return parse_update(f"INSERT {{ {text} }} WHERE {{}}")
        return parse_query(f"ASK {{ {text} }}")
    # near the recursion limit pyparsing fails with a TypeError on its own Suppress objects
    except (RecursionError, TypeError) as error:
        raise SparqlError(_TOO_LONG) from error
    except ParseBaseException as error:
        raise SparqlError("does not parse alone as a group graph pattern") from error


def _nodes(node: object) -> Iterator[object]:
    """``node`` and everything inside it: every nested parse node, list, tuple, set and dict value."""
    yield node
    if isinstance(node, dict):  # a CompValue is an ordered dict; the keys of a plain one are terms
        children: Iterable[object] = [*node.keys(), *node.values()]
    elif isinstance(node, list | tuple | set | frozenset | ParseResults):
        children = node
    else:
        return
    for child in children:
        yield from _nodes(child)


def _node_problem(node: object, template: bool, forbidden: Collection[URIRef]) -> str | None:
    problem = _any_node_problem(node)
    if problem or not template:
        return problem
    return _template_node_problem(node, forbidden)


def _any_node_problem(node: object) -> str | None:
    if isinstance(node, CompValue):
        if node.name in _GRAPH_NODES:
            return "contains GRAPH or SERVICE: a step works inside one graph"
        if node.name == _PREFIXED_NAME:
            return "has a prefixed name; write the full IRI in angle brackets"
    is_reserved = (
        isinstance(node, Variable)
        and node.startswith(_RESERVED_PREFIX)
        and str(node) != _GRAPH_VARIABLE
    )
    if is_reserved:
        return f"uses the reserved variable ?{node}; only ?{_GRAPH_VARIABLE} is open to it"
    return None


def _template_node_problem(node: object, forbidden: Collection[URIRef]) -> str | None:
    # rdf:nil is what ( ) parses to: a collection is a template's blank nodes, so the empty one goes too
    if isinstance(node, BNode) or node == RDF.nil:
        return "has a blank node (_:, [ ] or a collection), which a migration cannot mint"
    if isinstance(node, URIRef) and node in forbidden:
        return f"names {node}, one of the toolkit's own predicates, which a step may read but not write"
    return None
