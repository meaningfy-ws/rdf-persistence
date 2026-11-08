"""The session: guarded, tracked commits of whole graphs to one tenant database (PD-5, PD-7, PD-8).

The graph level (PD-7a) works on an aggregate's root IRI and its triples. An aggregate lives in
the one graph ``graph_iri(root)``; the tenant's root object lives in the tenant's meta graph and has
no registry entry. Every commit writes a fresh version token and is confirmed by an ``ASK`` for it.
"""

import uuid
from collections.abc import AsyncIterator, Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.query import ResultRow

from rdf_persistence.domain.exceptions import Conflict, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_core import Principal, RegistryEntry, RegistryKind
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.service.rp_service import ListPlan
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
    Iris,
    graph_iri,
    meta_graph_iri,
    registry_graph_iri,
    skolem_iri,
)
from rdf_persistence.domain.sparql import Triple, fill, term, term_list, triples_block
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.listing import listing_query
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
ASK_ANY = "ASK { GRAPH $graph { ?s ?p ?o } }"
ASK_TOKEN = "ASK { GRAPH $graph { $graph $p_version $token } }"
# One conditional insert: when the graph already holds a triple nothing is written, so two adds of
# one IRI cannot both succeed (PD-8c); the caller confirms with an ASK for its token.
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
    ) -> None:
        self._iris = iris
        self._store = store
        self._database = database
        self._tenant = tenant_iri
        self._principal = principal
        self._clock = clock
        self._registry = registry_graph_iri(tenant_iri)

    def _graph(self, iri: str) -> URIRef:
        """The graph of the aggregate ``iri``, or the meta graph for the tenant root."""
        if iri == self._tenant:
            return meta_graph_iri(self._tenant)
        if not self._iris.is_aggregate(self._tenant, iri):
            raise InvalidIri(f"{iri!r} is not an aggregate IRI of the tenant {self._tenant!r}")
        return graph_iri(iri)

    def _entries(
        self, iri: str, graph: URIRef, loaded_graphs: Sequence[URIRef]
    ) -> list[RegistryEntry]:
        if iri == self._tenant:
            return []
        return [
            RegistryEntry(graph=str(graph), kind=RegistryKind.AGGREGATE, owned_by=iri),
            *(
                RegistryEntry(graph=str(g), kind=RegistryKind.LOADED_GRAPH, owned_by=iri)
                for g in loaded_graphs
            ),
        ]

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

        The graph belongs to the aggregate once a commit passes the IRI as ``loaded_graphs``.

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            InvalidGraph: The data does not parse as ``rdf_format``; nothing is written.
            DatabaseGone: The tenant database does not exist.
        """
        self._graph(iri)
        parsed = await parse_graph(data, rdf_format)
        loaded = self._iris.mint_loaded_graph(self._tenant, iri)
        await self._store.put_graph(self._database, loaded, parsed)
        return loaded

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


@asynccontextmanager
async def open_session(
    store: Store,
    *,
    database: str,
    tenant_iri: str,
    principal: Principal,
    clock: Clock = utc_now,
    iris: Iris = DEFAULT_IRIS,
) -> AsyncIterator[Session]:
    """Open a session on the tenant database ``database`` for ``principal``; ``iris`` is the IRI policy
    (default: the default policy)."""
    yield Session(
        store,
        database=database,
        tenant_iri=tenant_iri,
        principal=principal,
        clock=clock,
        iris=iris,
    )
