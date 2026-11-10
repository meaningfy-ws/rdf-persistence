"""The sweep of one live tenant: the loaded graphs no commit owns and the blobs no graph names (live-tenant-sweep).

A loaded graph is an orphan when its IRI is one the policy mints for the tenant (for an aggregate or for
the tenant root alike), no registry entry owns it, and its load marker is older than the grace period
(or it has none).
A blob is an orphan when no graph of the tenant names its key in ``rp:fileKey`` and the bucket last
wrote it before the grace period. Both are deleted only when asked, separately; a dry run changes
nothing. The reads go in the safe order (PD-7): what is listed first is judged by what is read after,
so something committed in between is seen as owned or named.
"""

import logging
from datetime import UTC, datetime, timedelta

from rdflib import Literal, URIRef
from rdflib.query import ResultRow

from rdf_persistence.domain.exceptions import Conflict
from rdf_persistence.domain.generated.rp_tenancy import TenantState, TenantSweepReport
from rdf_persistence.domain.iris import Iris
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.session import utc_now
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)
_EPOCH = datetime.min.replace(tzinfo=UTC)  # a graph with no marker was loaded before markers: old

LIST_GRAPHS = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"
# Who owns a graph, and when a load put it, in one read of the registry.
READ_REGISTRY = """
SELECT ?g ?owner ?at WHERE {
  GRAPH $registry { { ?g $p_owned_by ?owner } UNION { ?g $p_loaded_at ?at } }
}
"""
READ_KEYS = "SELECT DISTINCT ?key WHERE { GRAPH ?g { ?s $p_file_key ?key } }"
# PD-5: the graph and its marker go only if, in this same update, no registry entry owns the graph.
DROP_ORPHAN = """
DELETE { GRAPH $graph { ?s ?p ?o } GRAPH $registry { $graph $p_loaded_at ?t } }
WHERE {
  GRAPH $graph { ?s ?p ?o }
  OPTIONAL { GRAPH $registry { $graph $p_loaded_at ?t } }
  FILTER NOT EXISTS { GRAPH $registry { $graph $p_owned_by ?root } }
}
"""
# PD-6: a marker is useless once a commit owns its graph, or when its graph is empty and the load old.
DROP_STALE_MARKERS = """
DELETE { GRAPH $registry { ?g $p_loaded_at ?t } }
WHERE {
  GRAPH $registry { ?g $p_loaded_at ?t }
  FILTER (
    EXISTS { GRAPH $registry { ?g $p_owned_by ?root } }
    || (?t < $cutoff && NOT EXISTS { GRAPH ?g { ?s ?p ?o } })
  )
}
"""


async def sweep_tenant(
    tenancy: Tenancy,
    store: Store,
    files: FileStore,
    iris: Iris,
    tenant: str,
    *,
    remove: bool = False,
    remove_blobs: bool = False,
    older_than: timedelta = timedelta(hours=1),
    clock=utc_now,
) -> TenantSweepReport:
    """Find the orphans of the active tenant ``tenant`` older than ``older_than``; delete the loaded
    graphs if ``remove`` and the blobs if ``remove_blobs``. Neither: a dry run.

    Pass ``remove_blobs`` only when every blob key of the tenant is stored in ``rp:fileKey``.

    Raises:
        NotFound: The tenant has no access record.
        Conflict: The tenant is being deleted.
        DatabaseGone: The tenant database does not exist.
        TenantGone: The tenant bucket does not exist; nothing was removed.
    """
    access, _ = await tenancy.get(tenant)
    if access.state != TenantState.ACTIVE:
        raise Conflict(f"{tenant} is {access.state}, not active")
    database = access.database_name  # the bucket has the same name
    cutoff = clock() - older_than
    registry = iris.registry(tenant)
    orphans = await _orphan_graphs(store, database, iris, tenant, cutoff)
    blobs = await _orphan_blobs(store, files, database, cutoff)
    if remove:
        for graph in orphans:
            _log_removal("sweep-loaded-graph", tenant, graph)
            await store.update(database, _drop_orphan(graph, registry))
        await store.update(database, _drop_stale_markers(registry, cutoff))
    skipped = await _delete_blobs(files, database, tenant, blobs) if remove_blobs else []
    return TenantSweepReport(
        tenant=tenant,
        older_than_seconds=int(older_than.total_seconds()),
        loaded_graphs=orphans,
        blobs=blobs,
        removed_loaded_graphs=remove,
        removed_blobs=remove_blobs,
        skipped_blobs=skipped,
    )


async def _orphan_graphs(
    store: Store, database: str, iris: Iris, tenant: str, cutoff: datetime
) -> list[str]:
    """The loaded graphs no entry owns that were loaded before ``cutoff``; listed first, then owners (PD-7)."""
    graphs = await _candidate_graphs(store, database, iris, tenant)
    owned, loaded_at = await _registry_view(store, database, iris.registry(tenant))
    return sorted(g for g in graphs if g not in owned and loaded_at.get(g, _EPOCH) < cutoff)


async def _orphan_blobs(
    store: Store, files: FileStore, database: str, cutoff: datetime
) -> list[str]:
    """The keys of blobs no graph names that were written before ``cutoff``; listed first, then keys (PD-7)."""
    listed = await files.list_blobs(database)
    named = await _named_keys(store, database)
    return sorted(b.file_key for b in listed if b.file_key not in named and b.modified < cutoff)


async def _rows(store: Store, database: str, text: str) -> list[ResultRow]:
    return [r for r in await store.query(database, text) if isinstance(r, ResultRow)]


async def _candidate_graphs(store: Store, database: str, iris: Iris, tenant: str) -> list[str]:
    """The tenant's loaded graphs, the tenant root's included (tenant-root-loads)."""
    found = (str(row.g) for row in await _rows(store, database, LIST_GRAPHS))
    return [g for g in found if iris.is_loaded_graph(tenant, g)]


async def _registry_view(
    store: Store, database: str, registry: URIRef
) -> tuple[set[str], dict[str, datetime]]:
    """The graphs a registry entry owns, and when each marked load put its graph."""
    text = fill(
        READ_REGISTRY,
        registry=term(registry),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        p_loaded_at=term(v.LOADED_AT),
    )
    owned: set[str] = set()
    loaded_at: dict[str, datetime] = {}
    for row in await _rows(store, database, text):
        if row.owner is not None:
            owned.add(str(row.g))
        at = _aware(row.at)
        if at is not None:  # an unreadable marker counts as none; of several, the youngest (RF-1)
            loaded_at[str(row.g)] = max(at, loaded_at.get(str(row.g), at))
    return owned, loaded_at


def _aware(value: object) -> datetime | None:
    """The marker's time if it is a timezone-aware datetime; ``None`` for anything another tool wrote."""
    if value is None:
        return None
    python = Literal(
        value
    ).toPython()  # an ill-typed literal comes back as its text, not a datetime
    return python if isinstance(python, datetime) and python.tzinfo is not None else None


async def _named_keys(store: Store, database: str) -> set[str]:
    text = fill(READ_KEYS, p_file_key=term(v.FILE_KEY))
    return {str(row.key) for row in await _rows(store, database, text)}


def _drop_orphan(graph: str, registry: URIRef) -> str:
    return fill(
        DROP_ORPHAN,
        graph=term(URIRef(graph)),
        registry=term(registry),
        p_loaded_at=term(v.LOADED_AT),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
    )


def _drop_stale_markers(registry: URIRef, cutoff: datetime) -> str:
    return fill(
        DROP_STALE_MARKERS,
        registry=term(registry),
        p_loaded_at=term(v.LOADED_AT),
        p_owned_by=term(v.REGISTRY_OWNED_BY),
        cutoff=term(Literal(cutoff)),
    )


async def _delete_blobs(files: FileStore, bucket: str, tenant: str, keys: list[str]) -> list[str]:
    """Delete ``keys``; the keys the object store refuses are logged and returned."""
    skipped: list[str] = []
    for key in keys:
        try:
            await files.delete(bucket, key)
        except ValueError:  # a key written by another tool, which the adapter will not delete
            log.warning(
                "the object store would not delete a blob; skipped",
                extra={"step": "sweep-blob-skipped", "tenant": tenant, "resource": key},
            )
            skipped.append(key)
        else:
            _log_removal("sweep-blob", tenant, key)
    return skipped


def _log_removal(step: str, tenant: str, resource: str) -> None:
    log.info(
        "removing an orphan of a live tenant",
        extra={"step": step, "tenant": tenant, "resource": resource},
    )
