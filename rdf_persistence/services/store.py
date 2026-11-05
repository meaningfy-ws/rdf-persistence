"""The triple-store port (PD-1): adapters implement it, the session and tenancy services use it.

Every method is async. SPARQL text arrives already built from ``domain.sparql``. A dataset is
a Fuseki database, named as in ``domain.iris``.
"""

from typing import Protocol

from rdflib import Graph, URIRef
from rdflib.query import Result


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

    async def create_dataset(self, name: str) -> None:
        """Create an empty dataset. Raises ``Conflict`` if it exists."""
        ...

    async def drop_dataset(self, name: str) -> None:
        """Delete a dataset and its data. Raises ``NotFound`` if it does not exist."""
        ...

    async def list_datasets(self) -> list[str]:
        """The names of all datasets."""
        ...
