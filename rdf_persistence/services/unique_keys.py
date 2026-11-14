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

from rdf_persistence.domain.exceptions import InvalidBody, KeyConflict
from rdf_persistence.domain.generated.rp_core import AggregateKey, RegistryKind
from rdf_persistence.domain.sparql import (
    SparqlTerm,
    Triple,
    count,
    fill,
    fragment,
    match_patterns,
    term,
    term_list,
    union,
)
from rdf_persistence.services import vocabulary as v

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


def claims(keys: Iterable[AggregateKey], iri: str, triples: Iterable[Triple]) -> list[KeyClaim]:
    """The claims of the root ``iri`` holding ``triples``: one per key of its type with a value for
    each predicate (PD-5); a key with a predicate that has no value claims nothing.

    Raises:
        InvalidBody: A key predicate has two values or more; nothing is sent (the shapes of the
            router refuse this earlier, so it can only come from a raw session call).
    """
    # a blank node is no value: in a pattern it would match anything, so it claims nothing
    own = [(p, o) for s, p, o in triples if str(s) == str(iri) and not isinstance(o, BNode)]
    types = {str(o) for p, o in own if p == RDF.type}
    found = [(key, _values_of(own, key, iri)) for key in keys if key.root_class in types]
    return [KeyClaim(key, str(iri), values) for key, values in found if values]


def _values_of(own: list[tuple[URIRef, Value]], key: AggregateKey, iri: str) -> tuple[Value, ...]:
    """The one value per predicate of ``key`` in ``own``, or none if a predicate has no value."""
    per_predicate = [[_plain(o) for p, o in own if str(p) == name] for name in key.key_predicates]
    if any(len(values) > 1 for values in per_predicate):
        raise InvalidBody(f"{iri} has more than one value for a slot of the key {key.key_name}")
    return tuple(values[0] for values in per_predicate) if all(per_predicate) else ()


def _identity(claim: KeyClaim) -> tuple[str, str, tuple[Value, ...]]:
    return claim.key.root_class, claim.key.key_name, claim.values


def same_value(claims: Sequence[KeyClaim]) -> list[KeyClaim]:
    """The claims another claim repeats: the same key and the same values for two roots (PD-6a).

    Two equal claims of one root (a key given twice) are no clash (D-4)."""
    roots: defaultdict[tuple, set[str]] = defaultdict(set)
    for claim in claims:
        roots[_identity(claim)].add(claim.root)
    return [claim for claim in claims if len(roots[_identity(claim)]) > 1]


def _held(
    claim: KeyClaim, registry: URIRef, excluded: Iterable[URIRef], **extra: SparqlTerm
) -> dict[str, SparqlTerm]:
    """The terms of ``KEY_HELD`` for ``claim``; ``extra`` are those of the template around it."""
    pairs = [*zip(map(URIRef, claim.key.key_predicates), claim.values, strict=True)]
    return {
        "values": match_patterns("key_root", [*pairs, (RDF.type, URIRef(claim.key.root_class))]),
        "registry": term(registry),
        "p_kind": term(v.REGISTRY_KIND),
        "aggregate": term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        "p_owned_by": term(v.REGISTRY_OWNED_BY),
        "excluded": term_list(excluded),
        **extra,
    }


def guard(claim: KeyClaim, registry: URIRef, excluded: Iterable[URIRef]) -> SparqlTerm:
    """The pattern that holds while no aggregate but the ``excluded`` roots holds the claimed values."""
    return fragment(_GUARD, **_held(claim, registry, excluded))


def diagnosis(claims: Sequence[KeyClaim], registry: URIRef, excluded: Iterable[URIRef]) -> str:
    """One ``SELECT`` of the indexes (``?claim``) of the claims some aggregate holds now (PD-9)."""
    excluded = list(excluded)
    branches = (
        fragment(_BRANCH, **_held(claim, registry, excluded, index=count(number)))
        for number, claim in enumerate(claims)
    )
    return fill(_DIAGNOSIS, branches=union(branches))


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
