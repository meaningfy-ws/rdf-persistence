"""The triple-store port (PD-1): adapters implement it, the session and tenancy services use it.

Every method is async. SPARQL text arrives already built from ``domain.sparql``. A dataset is
a Fuseki database, named as in ``domain.iris``.
"""

from typing import Protocol

from rdflib import Graph, URIRef
from rdflib.query import Result

from rdf_persistence.domain.exceptions import BadQuery, SparqlError


class Store(Protocol):
    """A SPARQL 1.1 store with a Graph Store endpoint and dataset administration."""

    async def query(self, dataset: str, sparql: str) -> Result:
        """Run a SELECT, ASK or CONSTRUCT.

        Returns:
            An rdflib ``Result``: iterate it for SELECT rows (``row.name``), read ``askAnswer`` for
            ASK, ``graph`` for CONSTRUCT.

        Raises:
            DatabaseGone: The dataset does not exist.
            BadQuery: The store refused the text.
            StoreUnavailable: The store is unreachable or failed.
        """
        ...

    async def update(self, dataset: str, sparql: str) -> None:
        """Run a SPARQL update; raises as ``query`` does."""
        ...

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        """Replace the named graph with ``graph`` (Graph Store PUT); raises as ``query`` does."""
        ...

    async def export_quads(self, dataset: str) -> bytes:
        """Every quad of the dataset as N-Quads, read once; the default graph passes through.

        Raises:
            DatabaseGone: The dataset does not exist.
            StoreUnavailable: The store is unreachable or failed.
        """
        ...

    async def import_quads(self, dataset: str, nquads: bytes) -> None:
        """Add the N-Quads to the dataset; raises as ``export_quads`` does."""
        ...

    async def create_dataset(self, name: str) -> None:
        """Create an empty dataset. Raises ``Conflict`` if it exists."""
        ...

    async def drop_dataset(self, name: str) -> None:
        """Delete a dataset and its data. Raises ``NotFound`` if it does not exist."""
        ...

    async def list_datasets(self) -> list[str]:
        """The names of all datasets."""
        ...


class ToolkitStore:
    """A ``Store`` for the SPARQL the toolkit writes itself, which no request can make malformed.

    Every value in such a text is a term (``domain.sparql``), so a store that refuses the text found
    a fault of the service, not a bad request: ``BadQuery`` becomes a ``SparqlError``, whose answer
    carries no detail. Everything else passes through.
    """

    def __init__(self, store: Store) -> None:
        self._store = store

    async def query(self, dataset: str, sparql: str) -> Result:
        try:
            return await self._store.query(dataset, sparql)
        except BadQuery as error:
            raise SparqlError("the store refused a query the toolkit wrote") from error

    async def update(self, dataset: str, sparql: str) -> None:
        try:
            await self._store.update(dataset, sparql)
        except BadQuery as error:
            raise SparqlError("the store refused an update the toolkit wrote") from error

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        await self._store.put_graph(dataset, graph_iri, graph)

    async def export_quads(self, dataset: str) -> bytes:
        return await self._store.export_quads(dataset)

    async def import_quads(self, dataset: str, nquads: bytes) -> None:
        await self._store.import_quads(dataset, nquads)

    async def create_dataset(self, name: str) -> None:
        await self._store.create_dataset(name)

    async def drop_dataset(self, name: str) -> None:
        await self._store.drop_dataset(name)

    async def list_datasets(self) -> list[str]:
        return await self._store.list_datasets()
