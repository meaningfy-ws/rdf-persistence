"""The pure SPARQL fragments of dependence: a part's pointer, the whole guard, the discovery query
and the no-late-part guard (dependent-aggregates PD-3, PD-6, PD-7).

A part is an aggregate with a pointer to its whole (``DependenceLink``). Nothing here reads or
writes a store: each function returns text filled with ``term``s, or a value parsed from a
solution; ``Transaction`` and ``Session`` own the calls, as they do for ``referrers``. A guard's
variables end in its index ``n`` in the request, so several guards never join.
"""

from collections.abc import Iterable, Sequence

from rdflib import URIRef
from rdflib.query import ResultRow

from rdf_persistence.core.domain.exceptions import InvalidBody
from rdf_persistence.core.domain.generated.rp_core import DependenceLink, RegistryKind
from rdf_persistence.core.domain.sparql import (
    SparqlTerm,
    Triple,
    count,
    fill,
    fragment,
    join,
    term,
    term_list,
)
from rdf_persistence.schema.services import vocabulary as v

# The whole exists (its graph holds a version) and is of a whole class when the request is
# applied (PD-3). Its variables end in $n, so guards never join.
_WHOLE_GUARD = (
    "GRAPH $graph { $graph $p_version ?wv$n . $whole a ?wt$n FILTER (?wt$n IN ($classes)) }"
)
# One level of the cascade: the parts of $wholes, each with its class and version (PD-6). The
# link pairs come first, so a store starts from the pointer triples.
_DISCOVERY = """
SELECT ?whole ?part ?type ?version WHERE {
  VALUES ?whole { $wholes }  VALUES (?type ?pointer) { $links }
  GRAPH ?g { ?part ?pointer ?whole ; a ?type . ?g $p_version ?version }
  GRAPH $registry { ?g $p_kind $aggregate ; $p_owned_by ?part }
} ORDER BY ?part LIMIT $limit
"""
# No aggregate of a part class points to $root from a graph this request does not remove (PD-7).
_NO_LATE_PART = """
FILTER NOT EXISTS {
  VALUES (?lt$n ?lp$n) { $links }
  GRAPH ?lg$n { ?lpart$n ?lp$n $root ; a ?lt$n }
  GRAPH $registry { ?lg$n $p_kind $aggregate ; $p_owned_by ?lpart$n }
  FILTER (?lg$n NOT IN ($removed))
}
"""


def pointer_of(part: str, triples: Iterable[Triple], link: DependenceLink) -> URIRef:
    """The whole the part ``part`` points to, read from its ``triples`` (PD-3).

    Raises:
        InvalidBody: The part has no value or several for the pointer, the value is not an IRI,
            or it is the part's own IRI (A-7). The message names the part only.
    """
    own, pointer = URIRef(part), URIRef(link.pointer)
    values = {o for s, p, o in triples if s == own and p == pointer}
    if len(values) != 1:
        raise InvalidBody(f"{part} needs exactly one value for {link.pointer}, not {len(values)}")
    (whole,) = values
    if not isinstance(whole, URIRef):
        raise InvalidBody(f"the value of {link.pointer} on {part} is not an IRI")
    if whole == own:
        raise InvalidBody(f"{part} cannot depend on itself")
    return whole


def link_of(types: Iterable[object], links: Sequence[DependenceLink]) -> DependenceLink | None:
    """The first of ``links`` whose part classes include one of ``types``, or ``None``: the
    aggregate is no part."""
    classes = {str(t) for t in types}
    return next((link for link in links if classes & set(link.part_classes)), None)


def whole_guard(whole_graph: URIRef, whole: URIRef, link: DependenceLink, n: int) -> SparqlTerm:
    """The guard of the part's request: ``whole`` holds a version in ``whole_graph`` and is of one
    of the link's whole classes (PD-3). Its variables end in ``n``, the guard's index."""
    return fragment(
        _WHOLE_GUARD,
        graph=term(whole_graph),
        p_version=term(v.VERSION),
        whole=term(whole),
        classes=term_list(URIRef(c) for c in sorted(link.whole_classes)),
        n=count(n),
    )


def link_pairs(links: Sequence[DependenceLink]) -> SparqlTerm:
    """The rows of a ``VALUES (?class ?pointer)`` list: one per part class of each link, sorted."""
    pairs = sorted({(c, link.pointer) for link in links for c in link.part_classes})
    return join(
        fragment("($cls $pointer)", cls=term(URIRef(c)), pointer=term(URIRef(p))) for c, p in pairs
    )


def discovery_query(
    wholes: Iterable[URIRef], links: Sequence[DependenceLink], registry: URIRef, limit: int
) -> str:
    """The query of one level of discovery: the parts of ``wholes`` as rows of ``?whole ?part ?type
    ?version`` (PD-6), at most ``limit + 1`` of them, so the caller sees the limit passed.

    Raises:
        SparqlError: A whole or a link is not a safe IRI, or ``limit`` is not a count.
    """
    return fill(
        _DISCOVERY,
        wholes=join(term(w) for w in sorted(set(wholes))),
        links=link_pairs(links),
        p_version=term(v.VERSION),
        registry=term(registry),
        p_kind=term(v.REGISTRY_KIND),
        aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        limit=count(limit + 1),
    )


def discovered(row: ResultRow) -> tuple[str, str, str, str]:
    """One solution of the discovery query as ``(whole, part, type, version)``; a version is a
    token (a UUID), not a number."""
    return (str(row.whole), str(row.part), str(row.type), str(row.version))


def whole_ask(whole_graph: URIRef, whole: URIRef, link: DependenceLink) -> str:
    """The question whether ``whole`` exists and is of a whole class now: the guard as an ``ASK``."""
    return fill("ASK { $guard }", guard=whole_guard(whole_graph, whole, link, 0))


def no_late_part_ask(
    root: URIRef, removed: Iterable[URIRef], links: Sequence[DependenceLink], registry: URIRef
) -> str:
    """The question whether no part of ``root`` outside ``removed`` is stored now (true: none)."""
    return fill("ASK { $guard }", guard=no_late_part_guard(root, removed, links, registry, 0))


def no_late_part_guard(
    root: URIRef,
    removed: Iterable[URIRef],
    links: Sequence[DependenceLink],
    registry: URIRef,
    n: int,
) -> SparqlTerm:
    """The guard of a delete for ``root``: no aggregate of a part class points to it from a graph
    outside ``removed`` (the graphs the request drops), i.e. no part was written after discovery
    (PD-7). Its variables end in ``n``, the guard's index."""
    return fragment(
        _NO_LATE_PART,
        links=link_pairs(links),
        root=term(root),
        registry=term(registry),
        p_kind=term(v.REGISTRY_KIND),
        aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        removed=term_list(sorted(set(removed))),
        n=count(n),
    )
