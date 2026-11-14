"""The use cases of the generic API on one aggregate: create, replace and delete (PD-13, PD-14).

A body becomes validated triples (``Documents``), a session commits them to the tenant's database,
and the aggregate is read back so the caller can answer with what was stored. What the route keeps
for itself is HTTP: negotiation, headers and status.
"""

from typing import cast

from linkml_runtime.linkml_model.meta import ClassDefinition
from rdflib import RDF, URIRef

from rdf_persistence.domain.exceptions import InvalidBody, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema_structure import iri_type_of
from rdf_persistence.services.session import Stored
from rdf_persistence.services.tenancy import Tenancy


class Aggregates:
    """Reads, creates, replaces and deletes the aggregates of a tenant on behalf of a principal."""

    def __init__(self, documents: Documents, tenancy: Tenancy, iris: Iris = DEFAULT_IRIS) -> None:
        self._documents = documents
        self._tenancy = tenancy
        self._iris = iris
        self._types = {rp_path: iri_type_of(cls) for rp_path, cls in documents.aggregates.items()}

    def iri_of(self, tenant: str, rp_path: str, aggregate_id: str) -> str:
        """The IRI of the aggregate served at ``rp_path`` whose id in a path is ``aggregate_id``.

        Raises:
            NotFound: ``aggregate_id`` is not an id the IRI policy mints.
        """
        return str(self._iris.aggregate(tenant, self._types[rp_path], rp_path, aggregate_id))

    def _require_class(self, stored: Stored, iri: str, cls: ClassDefinition) -> None:
        """A route answers only for an aggregate of its own class, or one derived from it (PD-30).

        The refusal reads as a missing aggregate, so it tells nothing of what else has the IRI.
        """
        graph, graph_iri, _ = stored
        if not self._documents.family(cls) & set(graph.objects(URIRef(iri), RDF.type)):
            raise NotFound(f"no graph {graph_iri}")

    async def read(
        self, tenant: str, principal: Principal, iri: str, cls: ClassDefinition
    ) -> Stored:
        """The aggregate ``iri``, as stored.

        Raises:
            NotFound: The aggregate has no graph, or is not of ``cls`` (a class derived from it will do).
        """
        async with self._tenancy.tenant_session(tenant, principal) as session:
            stored = await session.get_graph(iri)
        self._require_class(stored, iri, cls)
        return stored

    async def create(
        self,
        tenant: str,
        principal: Principal,
        cls: ClassDefinition,
        rp_path: str,
        data: bytes,
        media_type: str,
    ) -> tuple[str, Stored]:
        """Store the body ``data`` as a new aggregate of ``cls`` served at ``rp_path``; answers its minted IRI and what was stored.

        Raises:
            InvalidBody: The body is not a valid ``cls`` (see ``Documents.parse`` and ``validate``), or,
                with parts beside their root, names a part (PD-7).
        """
        iri = str(self._iris.mint_aggregate(tenant, iri_type_of(cls), rp_path))
        triples, named = await self._triples(tenant, data, media_type, cls, iri, creating=True)
        if named:
            raise InvalidBody(f"a new {cls.name} cannot name its parts, found {min(named)}")
        async with self._tenancy.tenant_session(tenant, principal) as session:
            await session.add_graph(iri, triples)
            return iri, await session.get_graph(iri)

    async def replace(
        self,
        tenant: str,
        principal: Principal,
        cls: ClassDefinition,
        iri: str,
        data: bytes,
        media_type: str,
        if_version: str,
    ) -> Stored:
        """Replace the aggregate ``iri`` by the body ``data`` if it is still at ``if_version``; answers what was stored.

        What the service stored in the aggregate's ``internal`` slots stays: no body can set them.

        Raises:
            InvalidBody: The body is not a valid ``cls`` rooted at ``iri``, or, with parts beside
                their root, names a part the aggregate does not store (PD-7), or, for a tenant's
                root, gives the tenant another label than its record has (PD-3) or is refused by a
                root validator.
            NotFound: The aggregate has no graph, or is not of ``cls`` (a class derived from it will do).
            Conflict: Its version is not ``if_version``; nothing changed.
        """
        triples, named = await self._triples(tenant, data, media_type, cls, iri, creating=False)
        if iri == tenant:
            await self._tenancy.vet_root(tenant, triples, principal)
        async with self._tenancy.tenant_session(tenant, principal) as session:
            found = await session.get_graph(iri)
            self._require_class(found, iri, cls)
            stored = found[0]
            foreign = named - set(stored.subjects())
            if foreign:
                raise InvalidBody(f"{min(foreign)} is not a part of the aggregate {iri}")
            kept = self._documents.internal_values(stored, triples)
            await session.replace_graph(iri, [*triples, *kept], if_version)
            return await session.get_graph(iri)

    async def remove(
        self,
        tenant: str,
        principal: Principal,
        iri: str,
        if_version: str,
        cls: ClassDefinition,
    ) -> None:
        """Delete the aggregate ``iri`` if it is still at ``if_version``.

        Raises:
            NotFound: The aggregate has no graph, or is not of ``cls`` (a class derived from it will do).
            Conflict: Its version is not ``if_version``; nothing changed.
        """
        async with self._tenancy.tenant_session(tenant, principal) as session:
            self._require_class(await session.get_graph(iri), iri, cls)
            await session.remove(iri, if_version)

    async def _triples(
        self,
        tenant: str,
        data: bytes,
        media_type: str,
        cls: ClassDefinition,
        iri: str,
        *,
        creating: bool,
    ) -> tuple[list[Triple], set[URIRef]]:
        """The validated triples of the body, rooted at ``iri``, and the subjects it names (see ``Documents.parse``)."""
        graph, named = await self._documents.parse(
            data, media_type, cls, iri, creating=creating, tenant=tenant
        )
        await self._documents.validate(graph)
        # rdflib types a graph's terms as Node; a parsed body holds only URIs, literals and blank nodes
        return cast(list[Triple], list(graph)), named
