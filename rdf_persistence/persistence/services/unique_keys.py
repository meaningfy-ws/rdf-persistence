"""Unique keys across the aggregates of a tenant: claims, guards and the diagnosis (PD-5 to PD-9).

A claim is the values one change of a transaction holds for one key. A guard refuses the commit
while another aggregate of the tenant holds the claimed values; it joins the transaction's guards,
so the check and the write are one request. Values are compared as RDF terms, after an
``xsd:string`` literal becomes the plain literal of the same text, since Fuseki treats the two as
one term and rdflib does not.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence

from rdflib import RDF, BNode, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.query import ResultRow

from rdf_persistence.core.domain.exceptions import InvalidBody, KeyConflict
from rdf_persistence.core.domain.generated.rp_core import AggregateKey, KeyDuplicate
from rdf_persistence.core.domain.sparql import (
    SparqlTerm,
    Triple,
    absent_patterns,
    count,
    fill,
    fragment_terms,
    join,
    match_patterns,
    optional_value_patterns,
    union,
    value_patterns,
    value_variables,
)
from rdf_persistence.schema.services import vocabulary as v

# One claimed value is held by an aggregate other than the excluded roots (PD-7). The value comes
# first, so a store finds it through an index instead of walking every registered graph; only an
# aggregate of the registry counts, never a loaded graph or a part. The variables bind nothing
# outside ``FILTER NOT EXISTS``, so several key guards share the names.
KEY_HELD = """
GRAPH ?key_graph { $values }
GRAPH $registry { ?key_graph $p_kind $aggregate ; $p_owned_by ?key_root }
FILTER (?key_root NOT IN ($excluded))
"""
_GUARD = "FILTER NOT EXISTS { " + KEY_HELD + " }"
_BRANCH = "{ " + KEY_HELD + " BIND($index AS ?claim) }"
_DIAGNOSIS = "SELECT DISTINCT ?claim WHERE { $branches }"
_ROOTS_SEPARATOR = " "  # no IRI holds a space
_DUPLICATES = (
    'SELECT $variables (GROUP_CONCAT(DISTINCT STR(?key_root); SEPARATOR="' + _ROOTS_SEPARATOR + '")'
    " AS ?key_roots) WHERE { $held } GROUP BY $variables HAVING (COUNT(DISTINCT ?key_root) > 1)"
)
Value = URIRef | Literal


class KeyClaim:
    """What one change claims: the ``values`` of ``key`` for ``root``, in the key's predicate order.

    Local to the transaction (PD-5): rdflib terms, which a generated model cannot hold. A plain
    class, not a ``NamedTuple``: the model guard refuses a hand-written record in ``services``.
    """

    __slots__ = ("key", "root", "values")

    def __init__(self, key: AggregateKey, root: str, values: tuple[Value, ...]) -> None:
        self.key, self.root, self.values = key, root, values


def _plain(value: Value) -> Value:
    """The one normalisation of PD-5: an ``xsd:string`` literal is the plain literal of its text."""
    if isinstance(value, Literal) and value.datatype == XSD.string:
        return Literal(str(value))
    return value


def claims_of(keys: Iterable[AggregateKey], iri: str, triples: Iterable[Triple]) -> list[KeyClaim]:
    """The claims of the root ``iri`` holding ``triples``: one per key of its type with a value for
    each predicate (PD-5); a key with a predicate that has no value claims nothing, unless it
    counts absences (``consider_nulls_inequal: false``): it claims ``ABSENT_KEY_VALUE`` there (PD-4).

    Raises:
        InvalidBody: A key predicate has two values or more; nothing is sent (the shapes of the
            router refuse this earlier, so it can only come from a raw session call).
    """
    # a blank node is no value: in a pattern it would match anything, so it claims nothing (a key
    # that counts absences claims ABSENT_KEY_VALUE for that slot instead, PD-4)
    own = [(p, o) for s, p, o in triples if str(s) == str(iri) and not isinstance(o, BNode)]
    types = {str(o) for p, o in own if p == RDF.type}
    found = [(key, _values_of(own, key, iri)) for key in keys if key.root_class in types]
    return [KeyClaim(key, str(iri), values) for key, values in found if values]


def _values_of(own: list[tuple[URIRef, Value]], key: AggregateKey, iri: str) -> tuple[Value, ...]:
    """The one value per predicate of ``key`` in ``own``; a predicate with no value gives none at all,
    or, for a key that counts absences, the ``ABSENT_KEY_VALUE`` (PD-4)."""
    per_predicate = [[_plain(o) for p, o in own if str(p) == name] for name in key.key_predicates]
    if any(len(values) > 1 for values in per_predicate):
        raise InvalidBody(f"{iri} has more than one value for a slot of the key {key.key_name}")
    if key.key_counts_absent:
        return _counted_values(per_predicate, key, iri)
    return tuple(values[0] for values in per_predicate) if all(per_predicate) else ()


def _counted_values(
    per_predicate: list[list[Value]], key: AggregateKey, iri: str
) -> tuple[Value, ...]:
    """The values of a key that counts absences: an empty slot is the ``ABSENT_KEY_VALUE`` (PD-4)."""
    if any(values and values[0] == v.ABSENT_KEY_VALUE for values in per_predicate):
        raise InvalidBody(
            f"{iri} holds the absent-value marker in a slot of the key {key.key_name}"
        )
    return tuple(values[0] if values else v.ABSENT_KEY_VALUE for values in per_predicate)


def _identity(claim: KeyClaim) -> tuple[str, str, tuple[Value, ...]]:
    return claim.key.root_class, claim.key.key_name, claim.values


def same_value(claims: Sequence[KeyClaim]) -> list[KeyClaim]:
    """The claims another claim repeats: the same key and the same values for two roots (PD-6a).

    Two equal claims of one root (a key given twice) are no clash (D-4)."""
    roots: defaultdict[tuple, set[str]] = defaultdict(set)
    for claim in claims:
        roots[_identity(claim)].add(claim.root)
    return [claim for claim in claims if len(roots[_identity(claim)]) > 1]


def _values(claim: KeyClaim) -> SparqlTerm:
    """The patterns that match a root holding the values of ``claim`` (``$values`` of ``KEY_HELD``)."""
    pairs = [*zip(map(URIRef, claim.key.key_predicates), claim.values, strict=True)]
    present = [(p, value) for p, value in pairs if value != v.ABSENT_KEY_VALUE]
    absent = [p for p, value in pairs if value == v.ABSENT_KEY_VALUE]
    held = match_patterns("key_root", [*present, (RDF.type, URIRef(claim.key.root_class))])
    return join([held, absent_patterns("key_root", absent)]) if absent else held


def guard(claim: KeyClaim, registry: URIRef, excluded: Iterable[URIRef]) -> SparqlTerm:
    """The pattern that holds while no aggregate but the ``excluded`` roots holds the claimed values."""
    held = v.key_held_terms(registry, values=_values(claim), excluded=excluded)
    return fragment_terms(_GUARD, held)


def diagnosis(claims: Sequence[KeyClaim], registry: URIRef, excluded: Iterable[URIRef]) -> str:
    """One ``SELECT`` of the indexes (``?claim``) of the claims some aggregate holds now (PD-9)."""
    excluded = list(excluded)
    branches = (
        fragment_terms(
            _BRANCH,
            v.key_branch_terms(
                registry, values=_values(claim), excluded=excluded, index=count(number)
            ),
        )
        for number, claim in enumerate(claims)
    )
    return fill(_DIAGNOSIS, branches=union(branches))


def duplicates_query(key: AggregateKey, registry: URIRef) -> str:
    """One read-only ``SELECT`` of the values of ``key`` two aggregates or more hold (PD-11): per
    group the values (``?v0`` …) and the roots, as IRIs joined by a space (``?key_roots``, which no
    IRI contains). It joins the registry as ``KEY_HELD`` does, and excludes no root."""
    predicates = [URIRef(name) for name in key.key_predicates]
    typed = match_patterns("key_root", [(RDF.type, URIRef(key.root_class))])
    if key.key_counts_absent:
        # the type binds ?key_root first: an OPTIONAL before it would match any node of the graph
        values = join([typed, optional_value_patterns("key_root", predicates, v.ABSENT_KEY_VALUE)])
    else:
        values = join([value_patterns("key_root", predicates), typed])
    return fill(
        _DUPLICATES,
        variables=value_variables(len(predicates)),
        held=fragment_terms(KEY_HELD, v.key_held_terms(registry, values=values, excluded=[])),
    )


def duplicates(key: AggregateKey, rows: Iterable[object]) -> list[KeyDuplicate]:
    """The ``KeyDuplicate`` of each row the ``duplicates_query`` of ``key`` answered."""
    return [
        KeyDuplicate(
            key_name=key.key_name,
            root_class=key.root_class,
            key_values=[str(row[n]) for n in range(len(key.key_predicates))],
            key_roots=sorted(str(row.key_roots).split(_ROOTS_SEPARATOR)),
        )
        for row in rows
        if isinstance(row, ResultRow)
    ]


def held(claims: Sequence[KeyClaim], rows: Iterable[object]) -> list[KeyClaim]:
    """The claims whose index (``?claim``) the ``rows`` of a ``diagnosis`` answer hold."""
    return [claims[int(row.claim)] for row in rows if isinstance(row, ResultRow)]


def key_conflict(claims: Iterable[KeyClaim], *, within_commit: bool) -> KeyConflict:
    """The refusal naming the roots of ``claims`` and their keys, in words and sorted (PD-8): no
    value, no holder, no graph. ``within_commit`` says the claims clash with each other; else some
    aggregate of the tenant holds the value."""
    claims = list(claims)
    roots = tuple(sorted({claim.root for claim in claims}))
    keys = tuple(sorted({claim.key.key_name for claim in claims}))
    named = f"{', '.join(roots)} for the key {', '.join(keys)}"
    text = (
        f"{named}: the changes of one commit claim the same value"
        if within_commit
        else f"{named}: the value claimed is held by another aggregate"
    )
    return KeyConflict(text, iris=roots, keys=keys)
