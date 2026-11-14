"""The session: guarded, tracked commits of whole graphs to one tenant database (PD-5, PD-7, PD-8).

The graph level (PD-7a) works on an aggregate's root IRI and its triples. An aggregate lives in
the one graph ``graph_iri(root)``; the tenant's root object lives in the tenant's meta graph, which
has no registry entry, while the graphs loaded for the root are registered like any aggregate's.
Every commit writes a fresh version token and is confirmed by an ``ASK`` for it. Several commits
can be made in one ``Transaction`` (``Session.transaction()``): one update request, all or nothing,
and ``request_text`` builds that request from the guards and operations of its changes (PD-2, PD-5).
A session opened with ``keys`` (unique keys across aggregates, see ``services.unique_keys``) adds one
guard per key a change claims, so the check and the write are one request; a clash is a ``KeyConflict``.
"""

import uuid
from collections.abc import AsyncIterator, Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.query import ResultRow

from rdf_persistence.domain.exceptions import Conflict, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_core import (
    AggregateKey,
    CommitMarker,
    PendingLoad,
    Principal,
    RegistryEntry,
    RegistryKind,
)
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import (
    AggregateHead,
    Condition,
    Filter,
    ListPlan,
    ListRequest,
)
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
    Iris,
    graph_iri,
    skolem_iri,
)
from rdf_persistence.domain.sparql import (
    SparqlTerm,
    Triple,
    count,
    fill,
    fragment,
    join,
    match_patterns,
    term,
    term_list,
    triples_block,
)
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.listing import (
    PAGE,
    Listings,
    condition_pairs,
    items_of,
    listing_query,
    total_of,
)
from rdf_persistence.services.loading import parse_graph
from rdf_persistence.services.store import Store
from rdf_persistence.services.unique_keys import (
    KeyClaim,
    claims_of,
    diagnosis,
    guard,
    held,
    key_conflict,
    same_value,
)

Clock = Callable[[], datetime]
# What a read of an aggregate answers: its triples with the bookkeeping, the graph that holds them
# (where the tracking statements are made, PD-7) and its version token.
Stored = tuple[Graph, URIRef, str]

READ_STORED = """
SELECT ?version ?created ?creator ?contributor WHERE {
  GRAPH $graph {
    $graph $p_version ?version .
    OPTIONAL { $graph $p_created ?created }
    OPTIONAL { $graph $p_creator ?creator }
    OPTIONAL { $graph $p_contributor ?contributor }
  }
}
"""
READ_GRAPH = "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH $graph { ?s ?p ?o } }"
READ_NAMED_KEYS = (
    "SELECT DISTINCT ?key WHERE { GRAPH ?g { ?s $p_file_key ?key } FILTER (?key IN ($keys)) }"
)
# The marker of a load (PD-2): when the graph was put, so a sweep can tell it from work in flight.
MARK_LOAD = "INSERT DATA { GRAPH $registry { $marker } }"
# Does any aggregate other than $root own one of the loaded graphs $graphs (PD-7)?
OWNED_ELSEWHERE = """
ASK { GRAPH $registry { ?g $p_owned_by ?owner ; $p_kind $loaded . FILTER (?g IN ($graphs) && ?owner != $root) } }
"""
READ_LOADED = "SELECT ?lg WHERE { GRAPH $registry { ?lg $p_owned_by $root ; $p_kind $loaded } }"
# A transaction is one update request of several operations, so a store applies them as one
# transaction (PD-2). Its first operation inserts a marker if every guard holds; every later
# operation matches only while the marker is there; the last one drops it. An operation that
# repeated its own guard could not work across roots: an add's own insert turns its guard false.
# The guards of a replace and a remove are the version it was read at; of an add, that no triple is
# there. Variables of an add's guard carry its number so the guards never join.
START = "INSERT { GRAPH $registry { $marker_triples } } WHERE { $guards }"
RELEASE = "DELETE { GRAPH $registry { $marker ?p ?o } } WHERE { GRAPH $registry { $marker ?p ?o } }"
_AT_VERSION = "GRAPH $graph { $graph $p_version $old }"
_ABSENT = "FILTER NOT EXISTS { GRAPH $graph { ?s$n ?p$n ?o$n } }"
_MARKED = "GRAPH $registry { $marker a $commit_marker }"
_LOADED_ENTRY = "GRAPH $registry { ?lg $p_owned_by $root ; $p_kind $loaded }"
_DROP_LOADED = """
DELETE {{ GRAPH ?lg {{ ?ls ?lp ?lo }} }}
WHERE {{ {marked} {entry} {unless} GRAPH ?lg {{ ?ls ?lp ?lo }} }}
"""
_DROP_ENTRIES = (
    f"DELETE {{ GRAPH $registry {{ ?e ?ep ?eo }} }} "
    f"WHERE {{ {_MARKED} GRAPH $registry {{ ?e $p_owned_by $root ; ?ep ?eo }} }}"
)
_DROP_GRAPH = (
    f"DELETE {{ GRAPH $graph {{ ?s ?p ?o }} }} WHERE {{ {_MARKED} GRAPH $graph {{ ?s ?p ?o }} }}"
)
# The old version triple stays until the last operation, as it did when each operation was guarded.
_DROP_GRAPH_BUT_VERSION = (
    "DELETE { GRAPH $graph { ?s ?p ?o } } "
    f"WHERE {{ {_MARKED} GRAPH $graph {{ ?s ?p ?o }} FILTER (!(?s = $graph && ?p = $p_version)) }}"
)
_WRITE_NEW = (
    f"INSERT {{ GRAPH $graph {{ $triples }} GRAPH $registry {{ $entries }} }} WHERE {{ {_MARKED} }}"
)
_DROP_OLD_VERSION = f"DELETE {{ GRAPH $graph {{ $graph $p_version $old }} }} WHERE {{ {_MARKED} }}"
_DROP_UNLISTED = _DROP_LOADED.format(
    marked=_MARKED, entry=_LOADED_ENTRY, unless="FILTER (?lg NOT IN ($kept))"
)
_DROP_ALL_LOADED = _DROP_LOADED.format(marked=_MARKED, entry=_LOADED_ENTRY, unless="")
REPLACE = ";\n".join(
    (_DROP_UNLISTED, _DROP_ENTRIES, _DROP_GRAPH_BUT_VERSION, _WRITE_NEW, _DROP_OLD_VERSION)
)
# Also empties the loaded graphs the root owns: they are part of the aggregate.
REMOVE = ";\n".join((_DROP_ALL_LOADED, _DROP_ENTRIES, _DROP_GRAPH))
# The records that depend on the removed root (a comment's target, PD-15): the graph and the registry
# entry of each registered aggregate whose root has one of the types $pairs with that link to $root.
# One operation whatever their number, and no version guard of theirs: they are never edited. It
# starts from the link to $root, so a tenant with no comment costs next to nothing (PD-30 item 6).
_DROP_DEPENDENTS = f"""
DELETE {{ GRAPH ?d {{ ?s ?p ?o }} GRAPH $registry {{ ?d ?ep ?eo }} }}
WHERE {{ {_MARKED}
  VALUES (?type ?link) {{ $pairs }}
  GRAPH ?d {{ ?c ?link $root ; a ?type }}
  GRAPH $registry {{ ?d $p_kind $aggregate ; $p_owned_by ?c }}
  {{ GRAPH ?d {{ ?s ?p ?o }} }} UNION {{ GRAPH $registry {{ ?d ?ep ?eo }} }} }}
"""
# What the transaction wrote, in one ASK (PD-3), and which graph holds what, for the diagnosis (PD-4).
CONFIRM = "ASK { $patterns }"
_HOLDS_TOKEN = "GRAPH $graph { $graph $p_version $new }"
# The registered aggregates among $members: each one's types and version (PD-6).
READ_HEADS = """
SELECT ?m ?type ?version WHERE {
  VALUES ?m { $members }
  GRAPH $registry { ?g $p_kind $aggregate ; $p_owned_by ?m }
  GRAPH ?g { ?m a ?type . ?g $p_version ?version }
}
"""
# The whole graph of every registered aggregate whose root has $predicate (with the object $object,
# or any), one row per triple and root (PD-28). The predicate pattern comes first, so the store
# starts from the triples that hold it and not from every aggregate.
READ_GRAPHS_WITH = """
SELECT DISTINCT ?root ?s ?p ?o WHERE {
  GRAPH ?g { ?root $predicate $object }
  GRAPH $registry { ?g $p_kind $aggregate ; $p_owned_by ?root }
  GRAPH ?g { ?s ?p ?o }
}
"""
# Is $iri an aggregate of class $type whose graph holds every statement of $patterns (PD-7)?
MATCHES = "ASK { GRAPH $graph { ?root a $type . $patterns FILTER (?root = $iri) } }"
# The same as a guard of a transaction: its variables carry $n, the guard's index in the transaction,
# so the guards never join.
_PRESENT = "GRAPH $graph { $graph $p_version ?held$n }"
_MATCH_GUARD = "GRAPH $graph { ?root$n a $type . $patterns FILTER (?root$n = $iri) }"
READ_VERSIONS = (
    "SELECT ?g ?version WHERE { VALUES ?g { $graphs } "
    "OPTIONAL { GRAPH ?g { ?g $p_version ?version } } }"
)


# Every aggregate whose graph holds a statement with $iri as its object (PD-3): the referrer, its
# class, the class of the statement's subject when that is a part (none when it is the referrer
# itself) and the predicate. The bookkeeping about the graph itself and rdf:type are not references.
# The reference pattern comes first, so the store starts from the triples that hold $iri.
READ_REFERRERS = """
SELECT DISTINCT ?referrer ?class ?subject_class ?p WHERE {
  GRAPH ?g { ?s ?p $iri . ?referrer a ?class . OPTIONAL { ?s a ?subject_class FILTER (?s != ?referrer) } }
  GRAPH $registry { ?g $p_kind $aggregate ; $p_owned_by ?referrer }
  FILTER (?s != ?g && ?p != $rdf_type)
  $dependents
}
"""
# A link of a dependent record (a comment's target) is dropped only for the record's class (PD-3).
_NOT_DEPENDENT = (
    "FILTER NOT EXISTS { VALUES (?dt ?dl) { $pairs } FILTER (?p = ?dl && ?class = ?dt) }"
)


# One link to a resource, as the store holds it: (referrer, referrer class, subject class or None,
# predicate), all IRIs; the schema names are the caller's to find.
ReferrerRow = tuple[str, str, str | None, str]


Dependents = Sequence[tuple[URIRef, URIRef]]


def _pair_values(pairs: Dependents) -> SparqlTerm:
    """The rows of a ``VALUES`` list, one ``(class predicate)`` per pair."""
    return join(fragment("($cls $link)", cls=term(c), link=term(p)) for c, p in pairs)


def _without_dependents(pairs: Dependents) -> SparqlTerm:
    """The clause that drops the links of ``(class, predicate)`` ``pairs``; none at all when there are none."""
    return fragment(_NOT_DEPENDENT, pairs=_pair_values(pairs)) if pairs else SparqlTerm("")


def utc_now() -> datetime:
    return datetime.now(UTC)


def registry_triples(entry: RegistryEntry) -> list[Triple]:
    """The statements of a registry entry, about the graph it names."""
    graph = URIRef(entry.graph)
    return [
        (graph, v.REGISTRY_GRAPH, graph),
        (graph, v.REGISTRY_KIND, v.REGISTRY_KIND_IRIS[RegistryKind(entry.kind)]),
        (graph, v.REGISTRY_OWNED_BY, URIRef(entry.owned_by)),
    ]


def marker_triples(marker: PendingLoad) -> list[Triple]:
    """The one statement of a load marker, about the graph it names."""
    return [(URIRef(marker.id), v.LOADED_AT, Literal(marker.loaded_at))]


def _tracking_triples(graph: URIRef, version: str, tracking: Tracked) -> list[Triple]:
    stamps = [(v.CREATED, tracking.created), (v.MODIFIED, tracking.modified)]
    people = [(v.CREATOR, [tracking.creator]), (v.CONTRIBUTOR, tracking.contributor)]
    return [
        (graph, v.VERSION, Literal(version)),
        *((graph, p, Literal(at)) for p, at in stamps if at is not None),
        *((graph, p, URIRef(who)) for p, whom in people for who in whom or [] if who is not None),
    ]


def _skolemised(graph: URIRef, triples: Iterable[Triple]) -> list[Triple]:
    """The triples with each blank node replaced by a fresh skolem IRI under ``graph`` (PD-8a)."""
    minted: dict[BNode, URIRef] = {}

    def named(node):
        if isinstance(node, BNode):
            minted.setdefault(node, skolem_iri(graph))
            return minted[node]
        return node

    return [(named(s), p, named(o)) for s, p, o in triples]


def without_bookkeeping(graph: URIRef, triples: Iterable[Triple]) -> list[Triple]:
    """``triples`` without the statements about ``graph`` that only the session writes."""
    return [t for t in triples if not (t[0] == graph and t[1] in v.BOOKKEEPING_PREDICATES)]


def payload_triples(
    graph: URIRef, version: str, tracking: Tracked, triples: Iterable[Triple]
) -> list[Triple]:
    """The caller's triples plus the version and tracking statements about ``graph`` (PD-7).

    Bookkeeping statements the caller sent about the graph IRI are dropped: only the session
    writes them, so a graph read from the store can be written back as it is. Blank nodes become
    skolem IRIs, since the replace update inserts its template once per matched row and would
    copy each blank node (PD-8a).
    """
    kept = without_bookkeeping(graph, triples)
    return [*_skolemised(graph, kept), *_tracking_triples(graph, version, tracking)]


def _entries_block(entries: Iterable[RegistryEntry]):
    return triples_block(t for entry in entries for t in registry_triples(entry))


def new_marker(at: datetime) -> CommitMarker:
    """The marker of one transaction: a fresh IRI, so no two transactions share one (PD-1)."""
    return CommitMarker(id=f"urn:uuid:{uuid.uuid4()}", started_at=at)


def commit_marker_triples(marker: CommitMarker) -> list[Triple]:
    """The statements of a commit marker: its type and when its transaction started."""
    subject = URIRef(marker.id)
    return [
        (subject, RDF.type, v.COMMIT_MARKER),
        (subject, v.STARTED_AT, Literal(marker.started_at)),
    ]


def request_text(
    registry: URIRef,
    marker: CommitMarker,
    guards: Iterable[SparqlTerm],
    operations: Iterable[str],
) -> str:
    """One update request: the guard operation, the marked ``operations``, the release (PD-2)."""
    start = fill(
        START,
        registry=term(registry),
        marker_triples=triples_block(commit_marker_triples(marker)),
        guards=join(guards),
    )
    release = fill(RELEASE, registry=term(registry), marker=term(URIRef(marker.id)))
    return ";\n".join([start, *operations, release])


def _fill_marked(
    template: str, graph: URIRef, registry: URIRef, marker: URIRef, **terms: SparqlTerm
) -> str:
    """``template`` with the terms every marked operation shares."""
    return fill(
        template,
        graph=term(graph),
        registry=term(registry),
        marker=term(marker),
        commit_marker=term(v.COMMIT_MARKER),
        **terms,
    )


def _owner_terms(root: URIRef) -> dict[str, SparqlTerm]:
    return {
        "root": term(root),
        "p_owned_by": term(v.REGISTRY_OWNED_BY),
        "p_kind": term(v.REGISTRY_KIND),
        "loaded": term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
    }


def add_parts(
    graph: URIRef,
    registry: URIRef,
    marker: URIRef,
    number: int,
    triples: Iterable[Triple],
    entries: Iterable[RegistryEntry],
) -> tuple[SparqlTerm, str]:
    """The guard (nothing is in ``graph``) and the marked operation that stores a new graph."""
    guard = _absent(graph, number)
    operations = _fill_marked(
        _WRITE_NEW,
        graph,
        registry,
        marker,
        triples=triples_block(triples),
        entries=_entries_block(entries),
    )
    return guard, operations


def _absent(graph: URIRef, number: int) -> SparqlTerm:
    """The pattern that holds while ``graph`` has no triple; ``number`` suffixes its variables, so
    the patterns of several changes never join."""
    return fragment(_ABSENT, graph=term(graph), n=count(number))


def _at_version(graph: URIRef, version: str) -> SparqlTerm:
    return fragment(
        _AT_VERSION, graph=term(graph), p_version=term(v.VERSION), old=term(Literal(version))
    )


def replace_parts(
    graph: URIRef,
    registry: URIRef,
    root: URIRef,
    marker: URIRef,
    old_version: str,
    triples: Iterable[Triple],
    entries: Iterable[RegistryEntry],
) -> tuple[SparqlTerm, str]:
    """The guard (``graph`` is at ``old_version``) and the marked operations that replace a graph,
    its root's registry entries and the loaded graphs not kept."""
    entries = list(entries)
    kept = [URIRef(e.graph) for e in entries if e.kind == RegistryKind.LOADED_GRAPH]
    operations = _fill_marked(
        REPLACE,
        graph,
        registry,
        marker,
        **_owner_terms(root),
        p_version=term(v.VERSION),
        old=term(Literal(old_version)),
        kept=term_list(kept),
        triples=triples_block(triples),
        entries=_entries_block(entries),
    )
    return _at_version(graph, old_version), operations


def remove_parts(
    graph: URIRef,
    registry: URIRef,
    root: URIRef,
    marker: URIRef,
    old_version: str,
    dependents: Dependents = (),
) -> tuple[SparqlTerm, str]:
    """The guard (``graph`` is at ``old_version``) and the marked operations that delete a graph and
    every registry entry the root owns, and the ``dependents`` that point at the root (none, none)."""
    operations = _fill_marked(REMOVE, graph, registry, marker, **_owner_terms(root))
    if dependents:
        operations += ";\n" + fill(
            _DROP_DEPENDENTS,
            registry=term(registry),
            marker=term(marker),
            commit_marker=term(v.COMMIT_MARKER),
            root=term(root),
            p_kind=term(v.REGISTRY_KIND),
            aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
            p_owned_by=term(v.REGISTRY_OWNED_BY),
            pairs=_pair_values(dependents),
        )
    return _at_version(graph, old_version), operations


class WriteGuard(Protocol):
    """What a transaction asks before it collects an add or a replace (PD-6): the triples to write.

    ``stored`` is ``None`` for an add, the stored tracking for a replace. It raises to refuse.
    """

    async def prepare(
        self, session: "Session", iri: str, triples: list[Triple], stored: Tracked | None
    ) -> list[Triple]: ...


class Session:
    """Reads and commits whole graphs of one tenant database on behalf of one principal."""

    def __init__(
        self,
        store: Store,
        *,
        database: str,
        tenant_iri: str,
        principal: Principal,
        clock: Clock,
        iris: Iris = DEFAULT_IRIS,
        listings: Listings | None = None,
        keys: Sequence[AggregateKey] = (),
        guards: WriteGuard | None = None,
        dependents: Dependents = (),
    ) -> None:
        self._dependents = tuple(dependents)  # (class, link) pairs a remove also drops (PD-15)
        self._keys = tuple(keys)
        self._write_guards = guards
        self._listings = listings
        self._iris = iris
        self._store = store
        self._database = database
        self._tenant = str(tenant_iri)  # a URIRef never equals a str (PD-12)
        self._principal = principal
        self._clock = clock
        self._registry = iris.registry(tenant_iri)

    def _graph(self, iri: str) -> URIRef:
        """The graph of the aggregate ``iri``, or the meta graph for the tenant root."""
        if str(iri) == self._tenant:
            return self._iris.meta(self._tenant)
        if not self._iris.is_aggregate(self._tenant, iri):
            raise InvalidIri(f"{iri!r} is not an aggregate IRI of the tenant {self._tenant!r}")
        return graph_iri(iri)

    def _entries(
        self, iri: str, graph: URIRef, loaded_graphs: Sequence[URIRef]
    ) -> list[RegistryEntry]:
        loaded = [
            RegistryEntry(graph=str(g), kind=RegistryKind.LOADED_GRAPH, owned_by=iri)
            for g in loaded_graphs
        ]
        if str(iri) == self._tenant:  # as in _graph: the root's graph is meta, never listed (DEC-2)
            return loaded
        return [RegistryEntry(graph=str(graph), kind=RegistryKind.AGGREGATE, owned_by=iri), *loaded]

    async def _check_commit(self, iri: str, loaded_graphs: Sequence[URIRef]) -> None:
        """Refuse what could alias another graph: an IRI the policy does not mint for an aggregate, a
        loaded graph it does not mint for this aggregate, or one another aggregate owns (PD-7)."""
        outside = [
            str(g)
            for g in loaded_graphs
            if not self._iris.is_loaded_graph(self._tenant, str(g), root=iri)
        ]
        if outside:
            raise InvalidIri(f"not loaded graphs the policy mints for {iri!r}: {outside}")
        if loaded_graphs and await self._ask(
            OWNED_ELSEWHERE,
            registry=term(self._registry),
            p_owned_by=term(v.REGISTRY_OWNED_BY),
            p_kind=term(v.REGISTRY_KIND),
            loaded=term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
            root=term(URIRef(iri)),
            graphs=term_list(loaded_graphs),
        ):
            raise InvalidIri(
                f"a loaded graph in {list(map(str, loaded_graphs))} is owned by another aggregate"
            )

    async def _registered_loaded(self, iri: str) -> list[URIRef]:
        """The loaded graphs the aggregate ``iri`` has registered."""
        text = fill(
            READ_LOADED,
            registry=term(self._registry),
            p_owned_by=term(v.REGISTRY_OWNED_BY),
            p_kind=term(v.REGISTRY_KIND),
            loaded=term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
            root=term(URIRef(iri)),
        )
        rows = [
            r for r in await self._store.query(self._database, text) if isinstance(r, ResultRow)
        ]
        return sorted(URIRef(r.lg) for r in rows)

    async def _ask(self, template: str, **terms) -> bool:
        result = await self._store.query(self._database, fill(template, **terms))
        return bool(result.askAnswer)

    async def _stored(self, graph: URIRef) -> tuple[str, Tracked]:
        """The version and tracking stored for ``graph``; raises NotFound if it holds none."""
        text = fill(
            READ_STORED,
            graph=term(graph),
            p_version=term(v.VERSION),
            p_created=term(v.CREATED),
            p_creator=term(v.CREATOR),
            p_contributor=term(v.CONTRIBUTOR),
        )
        rows = [
            r for r in await self._store.query(self._database, text) if isinstance(r, ResultRow)
        ]
        if not rows:
            raise NotFound(f"no graph {graph}")
        created = next((Literal(r.created).toPython() for r in rows if r.created is not None), None)
        creator = next((str(r.creator) for r in rows if r.creator is not None), None)
        contributors = sorted({str(r.contributor) for r in rows if r.contributor is not None})
        return str(rows[0].version), Tracked(
            created=created, creator=creator, contributor=contributors
        )

    async def get_graph(self, iri: str) -> Stored:
        """``(graph, graph_iri, version)`` of the aggregate: its stored triples with the bookkeeping,
        the IRI of the named graph that holds them, and its version token.

        The graph IRI is where the tracking statements are made (PD-7); hand it to
        ``Mapper.from_graph``.

        Raises:
            NotFound: The aggregate has no graph.
            DatabaseGone: The tenant database does not exist.
        """
        graph = self._graph(iri)
        result = await self._store.query(self._database, fill(READ_GRAPH, graph=term(graph)))
        stored = result.graph or Graph()
        version = stored.value(graph, v.VERSION)
        if version is None:
            raise NotFound(f"no graph {graph}")
        return stored, graph, str(version)

    async def page(self, plan: ListPlan) -> Graph:
        """The triples of the aggregates of one page of a listing, and the size of the whole listing.

        Raises:
            DatabaseGone: The tenant database does not exist.
        """
        result = await self._store.query(self._database, listing_query(self._registry, plan))
        return result.graph or Graph()

    async def referrer_rows(self, iri: str) -> list[ReferrerRow]:
        """What the tenant's aggregate graphs say that refers to ``iri``, one row per referrer, type and link.

        A link whose predicate and referrer class equal a ``dependents`` pair of this session (the
        pairs a remove drops with its target) is left out. No access is checked, and nothing is
        narrowed: the caller decides what to show.

        Raises:
            DatabaseGone: The tenant database does not exist.
        """
        text = fill(
            READ_REFERRERS,
            registry=term(self._registry),
            p_kind=term(v.REGISTRY_KIND),
            aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
            p_owned_by=term(v.REGISTRY_OWNED_BY),
            iri=term(URIRef(iri)),
            rdf_type=term(RDF.type),
            dependents=_without_dependents(self._dependents),
        )
        rows = [
            r for r in await self._store.query(self._database, text) if isinstance(r, ResultRow)
        ]
        return [
            (
                str(r.referrer),
                str(r["class"]),
                None if r.subject_class is None else str(r.subject_class),
                str(r.p),
            )
            for r in rows
        ]

    def not_aggregates(self, iris: Iterable[str]) -> list[str]:
        """The ``iris`` the policy does not mint for an aggregate of this tenant."""
        return [i for i in iris if not self._iris.is_aggregate(self._tenant, i)]

    async def heads(self, iris: Sequence[str]) -> list[AggregateHead]:
        """The IRI, types and version of each of ``iris`` that is a registered aggregate, in IRI order.

        An IRI with no stored aggregate has no head; no IRIs send no query. No access is checked.

        Raises:
            DatabaseGone: The tenant database does not exist.
        """
        if not iris:
            return []
        text = fill(
            READ_HEADS,
            registry=term(self._registry),
            p_kind=term(v.REGISTRY_KIND),
            aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
            p_owned_by=term(v.REGISTRY_OWNED_BY),
            p_version=term(v.VERSION),
            members=join(term(URIRef(i)) for i in iris),
        )
        rows = [
            r for r in await self._store.query(self._database, text) if isinstance(r, ResultRow)
        ]
        found: dict[str, tuple[set[str], str]] = {}
        for r in rows:
            types, _ = found.setdefault(str(r.m), (set(), str(r.version)))
            types.add(str(r.type))
        return [
            AggregateHead(head_iri=iri, head_types=sorted(types), head_version=version)
            for iri, (types, version) in sorted(found.items())
        ]

    async def graphs_with(self, predicate: URIRef, obj: URIRef | None = None) -> dict[str, Graph]:
        """The stored triples of each registered aggregate whose root has ``predicate`` (with
        ``obj`` as its object, when given), one ``Graph`` per root, keyed by the root's IRI.

        Triples about another subject inside an aggregate's graph stay in that aggregate's graph.
        No access is checked and no schema name is known: the caller decodes each graph.

        Raises:
            DatabaseGone: The tenant database does not exist.
        """
        text = fill(
            READ_GRAPHS_WITH,
            registry=term(self._registry),
            p_kind=term(v.REGISTRY_KIND),
            aggregate=term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
            p_owned_by=term(v.REGISTRY_OWNED_BY),
            predicate=term(predicate),
            object=SparqlTerm("?any") if obj is None else term(obj),
        )
        graphs: dict[str, Graph] = {}
        for row in await self._store.query(self._database, text):
            if isinstance(row, ResultRow):
                graphs.setdefault(str(row.root), Graph()).add((row.s, row.p, row.o))
        return graphs

    async def matches(self, iri: str, class_iri: str, conditions: Sequence[Condition]) -> bool:
        """Whether the aggregate ``iri`` is of exactly the class ``class_iri`` and holds every condition.

        The conditions are those of a ``ListPlan``, so this agrees with what ``find`` lists. No
        access is checked.

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            DatabaseGone: The tenant database does not exist.
        """
        return await self._ask(
            MATCHES,
            graph=term(self._graph(iri)),
            type=term(URIRef(class_iri)),
            patterns=match_patterns("root", condition_pairs(conditions)),
            iri=term(URIRef(iri)),
        )

    async def find(self, cls: type[BaseModel], **equals: object) -> list[str]:
        """The IRIs of the tenant's aggregates of ``cls`` whose slots equal ``equals``, in IRI order.

        A list or tuple value asks for all its items. Prohibitions are ignored (PD-6): a hidden
        duplicate is still a duplicate; check each IRI with ``require_aggregate`` before showing it.

        Not a snapshot: the pages are separate queries, so a concurrent write can slip past a
        uniqueness check made with it; declare a unique key across aggregates instead, which the
        commit enforces (``keys``, ``open_session``). With no filters it reads every aggregate of the class, so
        never pass caller input unfiltered.

        Raises:
            RuntimeError: The session was opened without listings.
            ValueError: ``cls`` is not an aggregate root with a path in the tenant databases, or a
                list value is empty.
            BadQuery: A name is not a slot a listing may filter on, or a value is not one of its slot.
            DatabaseGone: The tenant database does not exist.
        """
        if self._listings is None:
            raise RuntimeError("find needs a session opened with listings, e.g. by the service kit")
        definition = self._listings.served_root(cls.__name__)
        filters = _filters(equals)
        found: list[str] = []
        while True:
            request = ListRequest(filters=filters or None, limit=PAGE, offset=len(found))
            plan = self._listings.plan(definition, request)
            answer = await self.page(plan)
            items = items_of(answer, plan)
            found += [str(root) for root, _ in items]
            if not items or len(found) >= total_of(answer, plan):
                return found

    async def add_graph(
        self, iri: str, triples: Iterable[Triple], loaded_graphs: Sequence[URIRef] = ()
    ) -> str:
        """Store a new aggregate and register its ``loaded_graphs``; returns its first version.

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant, or a loaded
                graph is not one it mints for ``iri`` or is owned by another aggregate; nothing is
                written.
            Conflict: The aggregate already has a graph.
            KeyConflict: Another aggregate of the tenant holds a value of a key the aggregate claims.
            InvalidBody: A key slot has two values or more; nothing is written.
        """
        async with self.transaction() as transaction:
            return await transaction.add_graph(iri, triples, loaded_graphs)

    async def replace_graph(
        self,
        iri: str,
        triples: Iterable[Triple],
        if_version: str,
        loaded_graphs: Sequence[URIRef] | None = None,
    ) -> str:
        """Replace the aggregate if it still has ``if_version``; returns the new version token.

        ``loaded_graphs`` is the aggregate's loaded graphs afterwards: ``None`` keeps those already
        registered, a list replaces them (an empty one drops them all).

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant, or a loaded
                graph is not one it mints for ``iri`` or is owned by another aggregate; nothing is
                written.
            NotFound: The aggregate has no graph.
            Conflict: Its version is not ``if_version``; nothing changed.
            KeyConflict: Another aggregate of the tenant holds a value of a key the aggregate claims.
            InvalidBody: A key slot has two values or more; nothing is written.
        """
        async with self.transaction() as transaction:
            return await transaction.replace_graph(iri, triples, if_version, loaded_graphs)

    async def load_graph(self, iri: str, data: bytes, *, rdf_format: RdfFormat) -> URIRef:
        """Parse ``data`` into a new named graph of the aggregate ``iri``; returns its IRI.

        The graph belongs to the aggregate once a commit passes the IRI as ``loaded_graphs``. A marker
        with the load time goes to the registry first, for the live-tenant sweep.

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            InvalidGraph: The data does not parse as ``rdf_format``; nothing is written.
            DatabaseGone: The tenant database does not exist.
        """
        self._graph(iri)
        parsed = await parse_graph(data, rdf_format)
        loaded = self._iris.mint_loaded_graph(self._tenant, iri)
        marker = PendingLoad(id=str(loaded), loaded_at=self._clock())
        # first: a crash between the two leaves a marker with no graph, never a graph without one
        await self._store.update(
            self._database,
            fill(
                MARK_LOAD,
                registry=term(self._registry),
                marker=triples_block(marker_triples(marker)),
            ),
        )
        await self._store.put_graph(self._database, loaded, parsed)
        return loaded

    async def loaded_graph(self, iri: str, graph_iri: str) -> Graph:
        """The triples of ``graph_iri``, a graph loaded for the aggregate ``iri``.

        The session checks no access; the caller gates the read like ``get_graph`` (PD-7).

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            NotFound: ``graph_iri`` is not a graph loaded for the aggregate.
            DatabaseGone: The tenant database does not exist.
        """
        self._graph(iri)
        loaded = URIRef(graph_iri)
        if loaded not in await self._registered_loaded(iri):
            raise NotFound(f"{graph_iri} is not a graph loaded for {iri}")
        result = await self._store.query(self._database, fill(READ_GRAPH, graph=term(loaded)))
        return result.graph or Graph()

    async def loaded_graphs(self, iri: str) -> list[URIRef]:
        """The IRIs of the graphs loaded for the aggregate ``iri``, sorted by IRI (not load order).

        The session checks no access; the caller gates the read like ``get_graph`` (PD-7).

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            NotFound: The aggregate has no graph.
            DatabaseGone: The tenant database does not exist.
        """
        await self._stored(self._graph(iri))
        return await self._registered_loaded(iri)

    async def named_file_keys(self, keys: Iterable[str]) -> set[str]:
        """The members of ``keys`` that some graph of the tenant database still names in ``rp:fileKey``."""
        wanted = [Literal(k) for k in keys]
        if not wanted:
            return set()
        text = fill(READ_NAMED_KEYS, p_file_key=term(v.FILE_KEY), keys=term_list(wanted))
        rows = [
            r for r in await self._store.query(self._database, text) if isinstance(r, ResultRow)
        ]
        return {str(r.key) for r in rows}

    async def remove(self, iri: str, if_version: str) -> None:
        """Delete the aggregate's graph, loaded graphs and registry entries if it still has ``if_version``.

        Raises:
            NotFound: The aggregate has no graph.
            Conflict: Its version is not ``if_version``; nothing changed.
        """
        async with self.transaction() as transaction:
            await transaction.remove(iri, if_version)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["Transaction"]:
        """Collect aggregate writes and commit them as one update request, all or nothing (PD-5).

        ``add_graph``, ``replace_graph`` and ``remove`` on the yielded ``Transaction`` take the
        arguments of the session's own, check what those check and send nothing; leaving the block
        cleanly sends one request. An exception inside the block, or a block with no change, sends
        nothing.

        Raises:
            ValueError: (from a change) The aggregate already has a change in this transaction.
            RuntimeError: (from a change) The block has ended, so the change would be dropped.
            Conflict: A guard failed, so nothing changed; ``iris`` names the roots found conflicting.
            KeyConflict: (a ``Conflict``) A value of a key is claimed twice, or held by another
                aggregate; ``iris`` and ``keys`` name the roots and keys. The store's side of it is
                a diagnosis, like ``Conflict.iris``.
        """
        transaction = Transaction(self)
        try:
            yield transaction
            await transaction.commit()
        finally:
            transaction._end()


class Transaction:
    """Aggregate writes of one session, collected and sent as one update request (PD-2 to PD-6).

    The filled SPARQL fragments of the changes made so far are private; no public method takes
    SPARQL, so later pieces (key guards, outbox inserts) are added from inside ``services`` only
    (PD-6).

    Two limits of the diagnosis after a failed confirmation (PD-4), documented and not changed:

    * A transaction of removes only whose commit applied, and whose removed root another writer
      added again before the confirming ``ASK``, raises a ``Conflict`` though the commit applied
      (a false conflict, as for an overwritten write).
    * An add whose graph holds triples but no version triple raises a ``Conflict`` with empty
      ``iris`` and the message "lost a race with another writer", since the diagnosis finds no version to blame.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._marker = new_marker(session._clock())
        self._ended = False  # set when the block ends, committed or raised
        self._guards: list[SparqlTerm] = []
        self._operations: list[str] = []
        self._confirm: list[SparqlTerm] = []  # what holds when every change took effect (PD-3)
        # per graph, in the order of the changes: its root, the version the caller read (None for an
        # add), and the token the commit writes (none for a remove); read for the diagnosis (PD-4)
        self._roots: dict[URIRef, str] = {}
        self._read_at: dict[URIRef, str | None] = {}
        self._wrote: dict[URIRef, str] = {}
        self._required: dict[URIRef, str] = {}  # graph -> root of each ``_require_present`` (PD-25)
        self._key_claims: list[KeyClaim] = []  # what the changes claim of the session's keys (PD-6)

    def _end(self) -> None:
        """Refuse every later change: the block is over, so a change would be dropped."""
        self._ended = True

    def _collect(
        self,
        iri: str,
        graph: URIRef,
        read_at: str | None,
        wrote: str | None,
        parts: tuple[SparqlTerm, str],
        confirm: SparqlTerm,
    ) -> None:
        """Keep one change: its root, the version read, the token it writes (None for a remove),
        its guard and operations, and the pattern the commit confirms."""
        self._roots[graph] = str(iri)  # Conflict.iris holds str, whatever the caller passed (PD-7)
        self._read_at[graph] = read_at
        if wrote is not None:
            self._wrote[graph] = wrote
        self._guards.append(parts[0])
        self._operations.append(parts[1])
        self._confirm.append(confirm)

    def _require_open(self) -> None:
        if self._ended:
            raise RuntimeError("the transaction has ended; a change now would be dropped")

    def _claim(self, iri: str) -> URIRef:
        """The graph of ``iri``; a second change on the same graph, whatever string type, is refused."""
        self._require_open()
        graph = self._session._graph(iri)
        if graph in self._roots:
            raise ValueError(f"{iri} already has a change in this transaction")
        return graph

    @property
    def _marker_iri(self) -> URIRef:
        return URIRef(self._marker.id)

    @staticmethod
    def _holds(graph: URIRef, version: str) -> SparqlTerm:
        """The pattern that holds once ``graph`` carries the new ``version``."""
        return fragment(
            _HOLDS_TOKEN,
            graph=term(graph),
            p_version=term(v.VERSION),
            new=term(Literal(version)),
        )

    async def add_graph(
        self, iri: str, triples: Iterable[Triple], loaded_graphs: Sequence[URIRef] = ()
    ) -> str:
        """Collect a new aggregate and its ``loaded_graphs``; returns its first version.

        Raises what ``Session.add_graph`` raises before the request, and ``ValueError`` if the
        aggregate has a change in this transaction already.
        """
        session = self._session
        graph = self._claim(iri)
        await session._check_commit(iri, loaded_graphs)
        triples = list(triples)
        if session._write_guards is not None:
            triples = await session._write_guards.prepare(session, iri, triples, None)
        key_claims = claims_of(session._keys, iri, triples)
        version = str(uuid.uuid4())
        tracking = Tracked(created=session._clock(), creator=session._principal.id)
        parts = add_parts(
            graph,
            session._registry,
            self._marker_iri,
            len(self._roots),
            payload_triples(graph, version, tracking, triples),
            session._entries(iri, graph, loaded_graphs),
        )
        self._collect(iri, graph, None, version, parts, self._holds(graph, version))
        self._key_claims += key_claims
        return version

    async def replace_graph(
        self,
        iri: str,
        triples: Iterable[Triple],
        if_version: str,
        loaded_graphs: Sequence[URIRef] | None = None,
    ) -> str:
        """Collect the replacement of the aggregate if it still has ``if_version``; returns the new
        version. ``loaded_graphs`` is as in ``Session.replace_graph``."""
        session = self._session
        graph = self._claim(iri)
        await session._check_commit(iri, loaded_graphs or [])
        _, stored = await session._stored(graph)
        triples = list(triples)
        if session._write_guards is not None:
            triples = await session._write_guards.prepare(session, iri, triples, stored)
        key_claims = claims_of(session._keys, iri, triples)
        if loaded_graphs is None:
            loaded_graphs = await session._registered_loaded(iri)
        tracking = Tracked(
            created=stored.created,
            creator=stored.creator,
            modified=session._clock(),
            contributor=sorted({*(stored.contributor or []), session._principal.id}),
        )
        version = str(uuid.uuid4())
        parts = replace_parts(
            graph,
            session._registry,
            URIRef(iri),
            self._marker_iri,
            if_version,
            payload_triples(graph, version, tracking, triples),
            session._entries(iri, graph, loaded_graphs),
        )
        self._collect(iri, graph, if_version, version, parts, self._holds(graph, version))
        self._key_claims += key_claims
        return version

    async def remove(self, iri: str, if_version: str) -> None:
        """Collect the removal of the aggregate, its loaded graphs and entries, if it still has
        ``if_version``.

        Raises:
            NotFound: The aggregate has no graph.
        """
        session = self._session
        graph = self._claim(iri)
        await session._stored(graph)
        parts = remove_parts(
            graph,
            session._registry,
            URIRef(iri),
            self._marker_iri,
            if_version,
            session._dependents,
        )
        self._collect(iri, graph, if_version, None, parts, _absent(graph, len(self._roots)))

    def _require_present(self, iri: str) -> None:
        """Guard the commit on the aggregate ``iri`` still having a version when the request is
        applied; a commit refused for it names ``iri`` (PD-15). It collects no change.

        Do not use it on a graph the same transaction removes: the guards are checked when the
        request starts, before any of its operations, so the guard holds and tells nothing."""
        self._require_open()
        graph = self._session._graph(iri)
        number = count(len(self._guards))
        self._guards.append(
            fragment(_PRESENT, graph=term(graph), p_version=term(v.VERSION), n=number)
        )
        self._required[graph] = str(iri)

    def _require_match(self, iri: str, class_iri: str, conditions: Sequence[Condition]) -> None:
        """Guard the commit on ``iri`` being of exactly ``class_iri`` and holding every condition
        when the request is applied (the test of ``Session.matches``). It collects no change and
        names no one if it fails (PD-15)."""
        self._require_open()
        number = count(len(self._guards))
        patterns = match_patterns(f"root{number}", condition_pairs(conditions))
        self._guards.append(
            fragment(
                _MATCH_GUARD,
                graph=term(self._session._graph(iri)),
                type=term(URIRef(class_iri)),
                patterns=patterns,
                iri=term(URIRef(iri)),
                n=number,
            )
        )

    async def commit(self) -> None:
        """Send the request and confirm it (PD-2, PD-3); nothing is sent if there is no change.

        Raises:
            KeyConflict: Two changes claim one value of a key (nothing is sent), or another
                aggregate holds a value a change claims; nothing changed. The second kind is a
                diagnosis read after the refusal (PD-15).
            Conflict: A guard failed; nothing changed, and ``iris`` names the roots found conflicting.
        """
        if not self._roots:
            return
        session = self._session
        if clash := same_value(self._key_claims):
            raise key_conflict(clash, within_commit=True)
        excluded = self._excluded()
        key_guards = [guard(c, session._registry, excluded) for c in self._key_claims]
        await session._store.update(
            session._database,
            request_text(
                session._registry, self._marker, [*self._guards, *key_guards], self._operations
            ),
        )
        if not await session._ask(CONFIRM, patterns=join(self._confirm)):
            await self._diagnose()

    def _excluded(self) -> list[URIRef]:
        """The roots the transaction replaces or removes: their stored state is going away (PD-6)."""
        return [
            URIRef(root) for graph, root in self._roots.items() if self._read_at[graph] is not None
        ]

    async def _claims_held(self) -> list[KeyClaim]:
        """The claims of the transaction that another aggregate holds now (PD-9)."""
        session = self._session
        text = diagnosis(self._key_claims, session._registry, self._excluded())
        return held(self._key_claims, await session._store.query(session._database, text))

    async def _versions_found(self) -> dict[URIRef, str | None]:
        """The version each graph of the transaction holds now, ``None`` for a graph with none."""
        session = self._session
        text = fill(
            READ_VERSIONS,
            graphs=join(term(graph) for graph in {**self._roots, **self._required}),
            p_version=term(v.VERSION),
        )
        rows = [
            r
            for r in await session._store.query(session._database, text)
            if isinstance(r, ResultRow)
        ]
        return {URIRef(r.g): None if r.version is None else str(r.version) for r in rows}

    def _refused(self, graph: URIRef, found: str | None) -> str | None:
        """Why the graph, found at ``found``, refuses the change as it was read, in words about its
        root (PD-20a); None if it does not."""
        root, read_at = self._roots[graph], self._read_at[graph]
        if read_at is None:
            return None if found is None else f"{root} already exists"
        if found == read_at:
            return None
        who = "changed" if found is not None else "removed"
        return f"{root} was {who} by someone else since it was read"

    def _reasons(self, found: dict[URIRef, str | None]) -> dict[str, str]:
        """Root -> why the commit was refused for it, in the order of the sorted roots: the changes
        that no longer fit, and the required graphs that have no version now."""
        reasons = {}
        for graph in sorted(self._roots, key=self._roots.__getitem__):
            if (reason := self._refused(graph, found.get(graph))) is not None:
                reasons[self._roots[graph]] = reason
        for graph, root in self._required.items():
            if found.get(graph) is None:
                reasons[root] = f"{root} was removed by someone else since it was read"
        return dict(sorted(reasons.items()))

    async def _diagnose(self) -> None:
        """The confirmation failed: either nothing was written, or the commit applied and another
        writer changed a graph before the ``ASK``. Returns in the second case, else raises (PD-4)."""
        found = await self._versions_found()
        if any(found.get(graph) == token for graph, token in self._wrote.items()):
            return  # all or nothing: the commit applied, and a later writer changed some graph
        reasons = self._reasons(found)
        if not reasons and self._key_claims and (held := await self._claims_held()):
            raise key_conflict(held, within_commit=False)
        raise Conflict(
            "; ".join(reasons.values())
            or "the commit lost a race with another writer; read again and retry",
            iris=tuple(reasons),
        )


def _items(name: str, value: object) -> list[object]:
    """The values a filter asks for: a list or tuple gives its items, which may not be none."""
    items = list(value) if isinstance(value, list | tuple) else [value]
    if not items:
        raise ValueError(f"{name} is an empty list; give at least one value or leave it out")
    return items


def _filters(equals: dict[str, object]) -> list[Filter]:
    """One filter per value; a list or tuple gives one per item."""
    return [
        Filter(slot=name, value=_text(item))
        for name, value in equals.items()
        for item in _items(name, value)
    ]


def _text(value: object) -> str:
    """The RDF lexical form of a value (the mapper's); an enum gives its value."""
    return value.value if isinstance(value, Enum) else str(Literal(value))


@asynccontextmanager
async def open_session(
    store: Store,
    *,
    database: str,
    tenant_iri: str,
    principal: Principal,
    clock: Clock = utc_now,
    iris: Iris = DEFAULT_IRIS,
    listings: Listings | None = None,
    keys: Sequence[AggregateKey] = (),
    guards: WriteGuard | None = None,
    dependents: Dependents = (),
) -> AsyncIterator[Session]:
    """Open a session on the tenant database ``database`` for ``principal``; ``iris`` is the IRI policy
    (default: the default policy); ``listings`` lets the session ``find`` aggregates.

    ``keys`` are the keys across aggregates the commits enforce (``schema_structure.aggregate_keys``
    of the schema). With none, no key is enforced: a consumer opening sessions itself passes them.
    ``guards`` vet each add and replace (none: nothing is checked). ``dependents`` are the
    ``(class IRI, predicate)`` pairs whose records a remove drops with the aggregate they point at
    (none: a remove drops only the aggregate).
    """
    yield Session(
        store,
        database=database,
        tenant_iri=tenant_iri,
        principal=principal,
        clock=clock,
        iris=iris,
        listings=listings,
        keys=keys,
        guards=guards,
        dependents=dependents,
    )
