"""The use cases of the generic API on one aggregate: create, replace and delete (PD-13, PD-14).

A body becomes validated triples (``Documents``), a session commits them to the tenant's database,
and the aggregate is read back so the caller can answer with what was stored. What the route keeps
for itself is HTTP: negotiation, headers and status.
"""

from typing import cast

from linkml_runtime.linkml_model.meta import ClassDefinition

from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema_structure import iri_type_of
from rdf_persistence.services.session import Stored
from rdf_persistence.services.tenancy import Tenancy


class Aggregates:
    """Reads, creates, replaces and deletes the aggregates of a tenant on behalf of a principal."""

    def __init__(self, documents: Documents, tenancy: Tenancy, iris: Iris | None = None) -> None:
        self._documents = documents
        self._tenancy = tenancy
        self._iris = iris or DEFAULT_IRIS

    async def read(self, tenant: str, principal: Principal, iri: str) -> Stored:
        """The aggregate ``iri``, as stored.

        Raises:
            NotFound: The aggregate has no graph.
        """
        async with self._tenancy.tenant_session(tenant, principal) as session:
            return await session.get_graph(iri)

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
            InvalidBody: The body is not a valid ``cls`` (see ``Documents.parse`` and ``validate``).
        """
        iri = str(self._iris.mint_aggregate(tenant, iri_type_of(cls), rp_path))
        triples = await self._triples(tenant, data, media_type, cls, iri, creating=True)
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
            InvalidBody: The body is not a valid ``cls`` rooted at ``iri``.
            NotFound: The aggregate has no graph.
            Conflict: Its version is not ``if_version``; nothing changed.
        """
        triples = await self._triples(tenant, data, media_type, cls, iri, creating=False)
        async with self._tenancy.tenant_session(tenant, principal) as session:
            stored, _, _ = await session.get_graph(iri)
            kept = self._documents.internal_values(stored, triples)
            await session.replace_graph(iri, [*triples, *kept], if_version)
            return await session.get_graph(iri)

    async def remove(self, tenant: str, principal: Principal, iri: str, if_version: str) -> None:
        """Delete the aggregate ``iri`` if it is still at ``if_version``.

        Raises:
            NotFound: The aggregate has no graph.
            Conflict: Its version is not ``if_version``; nothing changed.
        """
        async with self._tenancy.tenant_session(tenant, principal) as session:
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
    ) -> list[Triple]:
        """The validated triples of the body, rooted at ``iri``."""
        graph = await self._documents.parse(
            data, media_type, cls, iri, creating=creating, tenant=tenant
        )
        await self._documents.validate(graph)
        # rdflib types a graph's terms as Node; a parsed body holds only URIs, literals and blank nodes
        return cast(list[Triple], list(graph))
