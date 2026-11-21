"""Referrers of a root: the read, the removal guard and the links of a commit's own changes
(delete-refuses-referenced PD-3 to PD-7; #226, #227).

A guard refuses the removal of a root of a refusing class while an aggregate graph the transaction
does not remove refers to it; it joins the transaction's guards, so the check and the write are one
request. The links a dependent record makes to its target (a comment's ``has_target``, the session's
``dependents`` pairs) are no referrers: the removal drops the record with its target. ``Transaction``
keeps the calls, as it does for the key guard of ``unique_keys``.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Protocol

from rdflib import RDF, URIRef
from rdflib.query import ResultRow

from rdf_persistence.core.domain.exceptions import InUse
from rdf_persistence.core.domain.generated.rp_core import RegistryKind
from rdf_persistence.core.domain.sparql import (
    SparqlTerm,
    Triple,
    count,
    fragment,
    join,
    term,
    term_list,
)
from rdf_persistence.persistence.services.generated.rows.rp_persistence_rows import ReferrerRow
from rdf_persistence.schema.services import vocabulary as v

# What the tenant's aggregate graphs say that refers to $iri: per solution, the referrer, its
# class, the class of the statement's subject when that is a part (none when it is the referrer
# itself) and the predicate. The bookkeeping about the graph itself and rdf:type are not references.
# The reference pattern comes first, so the store starts from the triples that hold $iri.
READ_REFERRERS = "SELECT DISTINCT ?referrer ?class ?subject_class ?p WHERE { $pattern }"
# The pattern of a referrer, shared by the read and by the removal guard (PD-3): its variables end
# in $n, empty for the read and the guard's index for a guard, so guards never join.
_REFERRERS = """
GRAPH ?g$n { ?s$n ?p$n $iri . ?referrer$n a ?class$n . OPTIONAL { ?s$n a ?subject_class$n FILTER (?s$n != ?referrer$n) } }
GRAPH $registry { ?g$n $p_kind $aggregate ; $p_owned_by ?referrer$n }
FILTER (?s$n != ?g$n && ?p$n != $rdf_type)
$dependents
"""
# A link of a dependent record (a comment's target) is dropped only for the record's class (PD-3).
_NOT_DEPENDENT = "FILTER NOT EXISTS { VALUES (?dt$n ?dl$n) { $pairs } FILTER (?p$n = ?dl$n && ?class$n = ?dt$n) }"
# No aggregate graph but the ones this transaction removes refers to the removed root $root (PD-3).
_REFERRER_GUARD = """
FILTER NOT EXISTS {
  GRAPH $graph { $root a ?t$n } VALUES ?t$n { $refusing }
  $referrers
  FILTER (?g$n NOT IN ($removed))
}
"""

# The referrers among the rows that refer to a root, which the caller may read: given the root's IRI
# and the rows, answers the referrer IRIs. Where none is given the session's full reach applies (PD-9).
Readable = Callable[[str, Sequence[ReferrerRow]], Awaitable[set[str]]]
# The (record class, predicate) pairs of a dependent record and the link to what it depends on.
Dependents = Sequence[tuple[URIRef, URIRef]]


class RemovalRefusal(Protocol):
    """The schema side of a refused removal (PD-7): which root classes refuse one while referenced,
    and the ``InUse`` that names the referrers. The session knows no schema; the kit builds this."""

    refusing: frozenset[URIRef]

    async def in_use(
        self,
        roots: Sequence[str],
        root: str,
        rows: Sequence[ReferrerRow],
        readable: Readable | None,
    ) -> InUse:
        """The refusal for the referenced ``roots``, naming the referrers in ``rows``, which refer to
        ``root``, one of them; ``readable`` judges who the caller may see (none: all)."""
        ...


def pair_values(pairs: Dependents) -> SparqlTerm:
    """The rows of a ``VALUES`` list, one ``(class predicate)`` per pair."""
    return join(fragment("($cls $link)", cls=term(c), link=term(p)) for c, p in pairs)


def _without_dependents(pairs: Dependents, n: SparqlTerm) -> SparqlTerm:
    """The clause that drops the links of ``(class, predicate)`` ``pairs``; none at all when there are none."""
    return fragment(_NOT_DEPENDENT, pairs=pair_values(pairs), n=n) if pairs else SparqlTerm("")


def referrers_pattern(
    iri: URIRef, registry: URIRef, dependents: Dependents, n: SparqlTerm
) -> SparqlTerm:
    """The pattern of the aggregates that refer to ``iri``, its variables ending in ``n``."""
    return fragment(
        _REFERRERS,
        iri=term(iri),
        registry=term(registry),
        p_kind=term(v.REGISTRY_KIND),
        aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        rdf_type=term(RDF.type),
        dependents=_without_dependents(dependents, n),
        n=n,
    )


def referrer_guards(
    removed: Mapping[URIRef, str],
    refusing: frozenset[URIRef],
    registry: URIRef,
    dependents: Dependents,
) -> list[SparqlTerm]:
    """One guard per root of the ``removed`` graphs (graph -> root): no aggregate graph outside
    ``removed`` refers to it, when it is typed with a ``refusing`` class (PD-3). None without a
    refusing class (G-3)."""
    if not refusing:
        return []
    return [
        fragment(
            _REFERRER_GUARD,
            graph=term(graph),
            root=term(URIRef(root)),
            refusing=join(term(c) for c in sorted(refusing)),
            referrers=referrers_pattern(URIRef(root), registry, dependents, count(n)),
            removed=term_list(sorted(removed)),
            n=count(n),
        )
        for n, (graph, root) in enumerate(sorted(removed.items(), key=lambda item: item[1]))
    ]


def row_of(result: ResultRow) -> ReferrerRow:
    """The row of one solution of ``READ_REFERRERS``."""
    subject = result.subject_class
    return ReferrerRow(
        referrer=str(result.referrer),
        referrer_class=str(result["class"]),
        subject_class=None if subject is None else str(subject),
        predicate=str(result.p),
    )


def row_key(row: ReferrerRow) -> tuple[str, str, str, str]:
    """The total sort key of a row: its four IRIs, an absent subject class first."""
    return (row.referrer, row.referrer_class, row.subject_class or "", row.predicate)


def _types_of(iri: str, triples: Sequence[Triple]) -> list[str]:
    """Every class the ``triples`` give the root ``iri``, sorted; one empty name when it has none."""
    own = URIRef(iri)
    return sorted({str(o) for s, p, o in triples if s == own and p == RDF.type}) or [""]


def _link_rows(iri: str, triples: Sequence[Triple]) -> list[tuple[str, ReferrerRow]]:
    """The links the ``triples`` of the root ``iri`` make to other IRIs: ``(target, row)``, the row as
    ``Session.referrer_rows`` reads it (its subject class is none for a link of the root itself). A
    root of several types makes one row per type, as the store answers one solution per ``rdf:type``."""
    own, root_classes = URIRef(iri), _types_of(iri, triples)
    part_class = {s: str(o) for s, p, o in triples if p == RDF.type and s != own}
    links = [(s, p, o) for s, p, o in triples if p != RDF.type and o != own]
    return [
        (
            str(o),
            ReferrerRow(
                referrer=iri,
                referrer_class=root_class,
                subject_class=part_class.get(s),
                predicate=str(p),
            ),
        )
        for s, p, o in links
        if isinstance(o, URIRef)
        for root_class in root_classes
    ]


def referrer_links(
    iri: str, triples: Sequence[Triple], dependents: Dependents
) -> list[tuple[str, ReferrerRow]]:
    """The links of ``_link_rows`` that are referrers: the link of a ``dependents`` pair is not, as in
    the store guard (PD-3)."""
    pairs = set(dependents)
    return [
        (target, row)
        for target, row in _link_rows(iri, triples)
        if (URIRef(row.referrer_class), URIRef(row.predicate)) not in pairs
    ]


def dependent_targets(iri: str, triples: Sequence[Triple], pairs: Dependents) -> set[str]:
    """The roots the record ``iri`` depends on: the objects of its links of a ``(class, predicate)``
    pair whose class it has, as the removal's drop of the dependents matches them (#226)."""
    own = URIRef(iri)
    types = {o for s, p, o in triples if s == own and p == RDF.type}
    links = {link for cls, link in pairs if cls in types}
    return {str(o) for s, p, o in triples if s == own and p in links}
