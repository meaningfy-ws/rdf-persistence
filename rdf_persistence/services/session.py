"""The session: guarded, tracked commits of whole graphs to one tenant database (PD-5, PD-7, PD-8).

The graph level (PD-7a) works on an aggregate's root IRI and its triples. An aggregate lives in
the one graph ``graph_iri(root)``; the tenant's root object lives in the tenant's meta graph and has
no registry entry. Every commit writes a fresh version token and is confirmed by an ``ASK`` for it.
"""

import uuid
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.query import ResultRow

from rdf_persistence.domain import vocabulary as v
from rdf_persistence.domain.errors import Conflict, NotFound
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_core import Principal, RegistryEntry, RegistryKind
from rdf_persistence.domain.iris import graph_iri, meta_graph_iri, registry_graph_iri
from rdf_persistence.domain.sparql import Triple, fill, term, triples_block
from rdf_persistence.services.store import Store

Clock = Callable[[], datetime]

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
ADD = "INSERT DATA { GRAPH $graph { $triples } GRAPH $registry { $entries } }"
# The guard, the delete of the old graph and entry, and the insert of the new ones, in one update.
REPLACE = """
DELETE { GRAPH $graph { ?s ?p ?o } GRAPH $registry { $graph ?ep ?eo } }
INSERT { GRAPH $graph { $triples } GRAPH $registry { $entries } }
WHERE {
  GRAPH $graph { $graph $p_version $old . ?s ?p ?o }
  OPTIONAL { GRAPH $registry { $graph ?ep ?eo } }
}
"""
REMOVE = """
DELETE { GRAPH $graph { ?s ?p ?o } GRAPH $registry { ?e ?ep ?eo } }
WHERE {
  GRAPH $graph { $graph $p_version $old . ?s ?p ?o }
  OPTIONAL { GRAPH $registry { ?e $p_owned_by $root ; ?ep ?eo } }
}
"""


def utc_now() -> datetime:
    return datetime.now(UTC)


def registry_triples(entry: RegistryEntry) -> list[Triple]:
    """The statements of a registry entry, about the graph it names."""
    graph = URIRef(entry.graph)
    return [
        (graph, v.REGISTRY_GRAPH, graph),
        (graph, v.REGISTRY_KIND, v.REGISTRY_KIND_IRIS[RegistryKind(entry.kind).value]),
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


def payload_triples(
    graph: URIRef, version: str, tracking: Tracked, triples: Iterable[Triple]
) -> list[Triple]:
    """The caller's triples plus the version and tracking statements about ``graph`` (PD-7).

    Bookkeeping statements the caller sent about the graph IRI are dropped: only the session
    writes them, so a graph read from the store can be written back as it is.

    Raises:
        ValueError: A triple has a blank node. The replace update inserts its template once per
            matched row, which would copy every blank node.
    """
    kept = [t for t in triples if not (t[0] == graph and t[1] in v.BOOKKEEPING_PREDICATES)]
    if any(isinstance(node, BNode) for triple in kept for node in triple):
        raise ValueError("an aggregate graph holds no blank nodes; give each node an IRI")
    return [*kept, *_tracking_triples(graph, version, tracking)]


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


def replace_text(
    graph: URIRef,
    registry: URIRef,
    old_version: str,
    triples: Iterable[Triple],
    entries: Iterable[RegistryEntry],
) -> str:
    """The guarded update that replaces a graph and its registry entries (the worked example)."""
    return fill(
        REPLACE,
        graph=term(graph),
        registry=term(registry),
        p_version=term(v.VERSION),
        old=term(Literal(old_version)),
        triples=triples_block(triples),
        entries=_entries_block(entries),
    )


def remove_text(graph: URIRef, registry: URIRef, root: URIRef, old_version: str) -> str:
    """The guarded update that deletes a graph and every registry entry the root owns."""
    return fill(
        REMOVE,
        graph=term(graph),
        registry=term(registry),
        root=term(root),
        p_version=term(v.VERSION),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        old=term(Literal(old_version)),
    )


class Session:
    """Reads and commits whole graphs of one tenant database on behalf of one principal."""

    def __init__(
        self, store: Store, *, database: str, tenant_iri: str, principal: Principal, clock: Clock
    ) -> None:
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
        if not iri.startswith(f"{self._tenant}/"):
            raise ValueError(f"{iri!r} is not inside the tenant {self._tenant!r}")
        return graph_iri(iri)

    def _entries(self, iri: str, graph: URIRef) -> list[RegistryEntry]:
        if iri == self._tenant:
            return []
        return [RegistryEntry(graph=str(graph), kind=RegistryKind.AGGREGATE, owned_by=iri)]

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

    async def get_graph(self, iri: str) -> tuple[Graph, str]:
        """The stored triples of the aggregate, bookkeeping included, and its version token.

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
        return stored, str(version)

    async def add_graph(self, iri: str, triples: Iterable[Triple]) -> str:
        """Store a new aggregate; returns its first version token.

        Raises:
            Conflict: The aggregate already has a graph.
        """
        graph = self._graph(iri)
        if await self._ask(ASK_ANY, graph=term(graph)):
            raise Conflict(f"{graph} already exists")
        version = str(uuid.uuid4())
        tracking = Tracked(created=self._clock(), creator=self._principal.id)
        payload = payload_triples(graph, version, tracking, triples)
        await self._store.update(
            self._database, add_text(graph, self._registry, payload, self._entries(iri, graph))
        )
        return version

    async def replace_graph(self, iri: str, triples: Iterable[Triple], if_version: str) -> str:
        """Replace the aggregate if it still has ``if_version``; returns the new version token.

        Raises:
            NotFound: The aggregate has no graph.
            Conflict: Its version is not ``if_version``; nothing changed.
        """
        graph = self._graph(iri)
        _, stored = await self._stored(graph)
        tracking = Tracked(
            created=stored.created,
            creator=stored.creator,
            modified=self._clock(),
            contributor=sorted({*(stored.contributor or []), self._principal.id}),
        )
        version = str(uuid.uuid4())
        payload = payload_triples(graph, version, tracking, triples)
        text = replace_text(graph, self._registry, if_version, payload, self._entries(iri, graph))
        await self._store.update(self._database, text)
        if not await self._ask(
            ASK_TOKEN, graph=term(graph), p_version=term(v.VERSION), token=term(Literal(version))
        ):
            raise Conflict(f"{graph} is no longer at version {if_version}")
        return version

    async def remove(self, iri: str, if_version: str) -> None:
        """Delete the aggregate's graph and registry entries if it still has ``if_version``.

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
) -> AsyncIterator[Session]:
    """Open a session on the tenant database ``database`` for ``principal``."""
    yield Session(store, database=database, tenant_iri=tenant_iri, principal=principal, clock=clock)
