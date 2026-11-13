"""The session: guarded, tracked commits of whole graphs to one tenant database (PD-5, PD-7, PD-8).

The graph level (PD-7a) works on an aggregate's root IRI and its triples. An aggregate lives in
the one graph ``graph_iri(root)``; the tenant's root object lives in the tenant's meta graph, which
has no registry entry, while the graphs loaded for the root are registered like any aggregate's.
Every commit writes a fresh version token and is confirmed by an ``ASK`` for it.
"""

import uuid
from collections.abc import AsyncIterator, Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.query import ResultRow

from rdf_persistence.domain.exceptions import Conflict, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_core import (
    PendingLoad,
    Principal,
    RegistryEntry,
    RegistryKind,
)
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import Filter, ListPlan, ListRequest
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
    Iris,
    graph_iri,
    skolem_iri,
)
from rdf_persistence.domain.sparql import Triple, fill, term, term_list, triples_block
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.listing import PAGE, Listings, items_of, listing_query, total_of
from rdf_persistence.services.loading import parse_graph
from rdf_persistence.services.store import Store

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
ASK_ANY = "ASK { GRAPH $graph { ?s ?p ?o } }"
ASK_TOKEN = "ASK { GRAPH $graph { $graph $p_version $token } }"
# One conditional insert: when the graph already holds a triple nothing is written, so two adds of
# one IRI cannot both succeed (PD-8c); the caller confirms with an ASK for its token.
# The marker of a load (PD-2): when the graph was put, so a sweep can tell it from work in flight.
MARK_LOAD = "INSERT DATA { GRAPH $registry { $marker } }"
ADD = """
INSERT { GRAPH $graph { $triples } GRAPH $registry { $entries } }
WHERE { FILTER NOT EXISTS { GRAPH $graph { ?s ?p ?o } } }
"""
# Does any aggregate other than $root own one of the loaded graphs $graphs (PD-7)?
OWNED_ELSEWHERE = """
ASK { GRAPH $registry { ?g $p_owned_by ?owner ; $p_kind $loaded . FILTER (?g IN ($graphs) && ?owner != $root) } }
"""
READ_LOADED = "SELECT ?lg WHERE { GRAPH $registry { ?lg $p_owned_by $root ; $p_kind $loaded } }"
# REPLACE and REMOVE are one update request of several operations, so a store applies them as one
# transaction. Every operation repeats the version guard, and the order keeps it true for each: the
# loaded graphs go first because they are found through the registry entries, the old version
# triple goes last. Separate operations avoid joining the graph, the registry and the loaded graphs
# into one product of rows.
_GUARD = "GRAPH $graph { $graph $p_version $old }"
_LOADED_ENTRY = "GRAPH $registry { ?lg $p_owned_by $root ; $p_kind $loaded }"
_DROP_LOADED = """
DELETE {{ GRAPH ?lg {{ ?ls ?lp ?lo }} }}
WHERE {{ {guard} {entry} {unless} GRAPH ?lg {{ ?ls ?lp ?lo }} }}
"""
_DROP_ENTRIES = (
    f"DELETE {{ GRAPH $registry {{ ?e ?ep ?eo }} }} "
    f"WHERE {{ {_GUARD} GRAPH $registry {{ ?e $p_owned_by $root ; ?ep ?eo }} }}"
)
_DROP_GRAPH = (
    f"DELETE {{ GRAPH $graph {{ ?s ?p ?o }} }} WHERE {{ {_GUARD} GRAPH $graph {{ ?s ?p ?o }} }}"
)
# The old version triple stays, so the guard holds, until the last operation.
_DROP_GRAPH_BUT_VERSION = (
    "DELETE { GRAPH $graph { ?s ?p ?o } } "
    f"WHERE {{ {_GUARD} GRAPH $graph {{ ?s ?p ?o }} FILTER (!(?s = $graph && ?p = $p_version)) }}"
)
_WRITE_NEW = (
    f"INSERT {{ GRAPH $graph {{ $triples }} GRAPH $registry {{ $entries }} }} WHERE {{ {_GUARD} }}"
)
_DROP_OLD_VERSION = f"DELETE {{ GRAPH $graph {{ $graph $p_version $old }} }} WHERE {{ {_GUARD} }}"
_DROP_UNLISTED = _DROP_LOADED.format(
    guard=_GUARD, entry=_LOADED_ENTRY, unless="FILTER (?lg NOT IN ($kept))"
)
_DROP_ALL_LOADED = _DROP_LOADED.format(guard=_GUARD, entry=_LOADED_ENTRY, unless="")
REPLACE = ";\n".join(
    (_DROP_UNLISTED, _DROP_ENTRIES, _DROP_GRAPH_BUT_VERSION, _WRITE_NEW, _DROP_OLD_VERSION)
)
# Also empties the loaded graphs the root owns: they are part of the aggregate.
REMOVE = ";\n".join((_DROP_ALL_LOADED, _DROP_ENTRIES, _DROP_GRAPH))


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


def payload_triples(
    graph: URIRef, version: str, tracking: Tracked, triples: Iterable[Triple]
) -> list[Triple]:
    """The caller's triples plus the version and tracking statements about ``graph`` (PD-7).

    Bookkeeping statements the caller sent about the graph IRI are dropped: only the session
    writes them, so a graph read from the store can be written back as it is. Blank nodes become
    skolem IRIs, since the replace update inserts its template once per matched row and would
    copy each blank node (PD-8a).
    """
    kept = [t for t in triples if not (t[0] == graph and t[1] in v.BOOKKEEPING_PREDICATES)]
    return [*_skolemised(graph, kept), *_tracking_triples(graph, version, tracking)]


def _entries_block(entries: Iterable[RegistryEntry]):
    return triples_block(t for entry in entries for t in registry_triples(entry))


def add_text(
    graph: URIRef, registry: URIRef, triples: Iterable[Triple], entries: Iterable[RegistryEntry]
) -> str:
    """The update that stores a new graph and its registry entries."""
    return fill(
        ADD,
        graph=term(graph),
        registry=term(registry),
        triples=triples_block(triples),
        entries=_entries_block(entries),
    )


def _fill_guarded(
    template: str, graph: URIRef, registry: URIRef, root: URIRef, old_version: str, **terms
) -> str:
    """``template`` with the terms REPLACE and REMOVE share: the graph, registry, root and guard."""
    return fill(
        template,
        graph=term(graph),
        registry=term(registry),
        root=term(root),
        p_version=term(v.VERSION),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        p_kind=term(v.REGISTRY_KIND),
        loaded=term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
        old=term(Literal(old_version)),
        **terms,
    )


def replace_text(
    graph: URIRef,
    registry: URIRef,
    root: URIRef,
    old_version: str,
    triples: Iterable[Triple],
    entries: Iterable[RegistryEntry],
) -> str:
    """The guarded update that replaces a graph, its root's registry entries and dropped loads."""
    entries = list(entries)
    kept = [URIRef(e.graph) for e in entries if e.kind == RegistryKind.LOADED_GRAPH]
    return _fill_guarded(
        REPLACE,
        graph,
        registry,
        root,
        old_version,
        kept=term_list(kept),
        triples=triples_block(triples),
        entries=_entries_block(entries),
    )


def remove_text(graph: URIRef, registry: URIRef, root: URIRef, old_version: str) -> str:
    """The guarded update that deletes a graph and every registry entry the root owns."""
    return _fill_guarded(REMOVE, graph, registry, root, old_version)


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
    ) -> None:
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

    async def find(self, cls: type[BaseModel], **equals: object) -> list[str]:
        """The IRIs of the tenant's aggregates of ``cls`` whose slots equal ``equals``, in IRI order.

        A list or tuple value asks for all its items. Prohibitions are ignored (PD-6): a hidden
        duplicate is still a duplicate; check each IRI with ``require_aggregate`` before showing it.

        Not a snapshot: the pages are separate queries, so a concurrent write can slip past a
        uniqueness check made with it. With no filters it reads every aggregate of the class, so
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
        """
        graph = self._graph(iri)
        await self._check_commit(iri, loaded_graphs)
        version = str(uuid.uuid4())
        tracking = Tracked(created=self._clock(), creator=self._principal.id)
        payload = payload_triples(graph, version, tracking, triples)
        entries = self._entries(iri, graph, loaded_graphs)
        await self._store.update(self._database, add_text(graph, self._registry, payload, entries))
        if not await self._ask(
            ASK_TOKEN, graph=term(graph), p_version=term(v.VERSION), token=term(Literal(version))
        ):
            raise Conflict(f"{graph} already exists")
        return version

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
        """
        graph = self._graph(iri)
        await self._check_commit(iri, loaded_graphs or [])
        _, stored = await self._stored(graph)
        if loaded_graphs is None:
            loaded_graphs = await self._registered_loaded(iri)
        tracking = Tracked(
            created=stored.created,
            creator=stored.creator,
            modified=self._clock(),
            contributor=sorted({*(stored.contributor or []), self._principal.id}),
        )
        version = str(uuid.uuid4())
        payload = payload_triples(graph, version, tracking, triples)
        entries = self._entries(iri, graph, loaded_graphs)
        text = replace_text(graph, self._registry, URIRef(iri), if_version, payload, entries)
        await self._store.update(self._database, text)
        if not await self._ask(
            ASK_TOKEN, graph=term(graph), p_version=term(v.VERSION), token=term(Literal(version))
        ):
            raise Conflict(f"{graph} is no longer at version {if_version}")
        return version

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
        graph = self._graph(iri)
        await self._stored(graph)
        text = remove_text(graph, self._registry, URIRef(iri), if_version)
        await self._store.update(self._database, text)
        if await self._ask(ASK_ANY, graph=term(graph)):
            raise Conflict(f"{graph} is no longer at version {if_version}")


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
) -> AsyncIterator[Session]:
    """Open a session on the tenant database ``database`` for ``principal``; ``iris`` is the IRI policy
    (default: the default policy); ``listings`` lets the session ``find`` aggregates."""
    yield Session(
        store,
        database=database,
        tenant_iri=tenant_iri,
        principal=principal,
        clock=clock,
        iris=iris,
        listings=listings,
    )
