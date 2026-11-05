"""In-memory fakes of the toolkit's ports, for unit tests that must not touch the network."""

from collections import defaultdict

from pyparsing import ParseException
from rdflib import Dataset, Graph, URIRef
from rdflib.plugins.sparql import prepareQuery, prepareUpdate
from rdflib.query import Result

from rdf_persistence.domain.errors import (
    BadQuery,
    Conflict,
    DatabaseGone,
    NotFound,
    PersistenceError,
)


class FakeStore:
    """A ``Store`` over one rdflib ``Dataset`` per dataset name, with failure injection.

    ``on(operation, error, times)`` makes the next ``times`` calls of ``operation`` raise ``error``;
    ``sent(operation)`` lists what each call was given (SPARQL text, graph IRI or dataset name),
    including the calls that failed.
    """

    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}
        self._failures: defaultdict[str, list[PersistenceError]] = defaultdict(list)
        self._sent: defaultdict[str, list[str]] = defaultdict(list)

    def on(self, operation: str, error: PersistenceError, times: int = 1) -> None:
        """Raise ``error`` on the next ``times`` calls of ``operation``."""
        self._failures[operation].extend([error] * times)

    def sent(self, operation: str) -> list[str]:
        """What each call of ``operation`` was given, in order."""
        return list(self._sent[operation])

    def _enter(self, operation: str, payload: str) -> None:
        self._sent[operation].append(payload)
        if self._failures[operation]:
            raise self._failures[operation].pop(0)

    def _dataset(self, name: str) -> Dataset:
        if name not in self._datasets:
            raise DatabaseGone(f"no dataset {name}")
        return self._datasets[name]

    async def query(self, dataset: str, sparql: str) -> Result:
        self._enter("query", sparql)
        data = self._dataset(dataset)
        try:
            return data.query(prepareQuery(sparql))
        except ParseException as error:
            raise BadQuery(str(error)) from error

    async def update(self, dataset: str, sparql: str) -> None:
        self._enter("update", sparql)
        data = self._dataset(dataset)
        try:
            data.update(prepareUpdate(sparql))
        except ParseException as error:
            raise BadQuery(str(error)) from error

    async def put_graph(self, dataset: str, graph_iri: URIRef, graph: Graph) -> None:
        self._enter("put_graph", str(graph_iri))
        target = self._dataset(dataset).graph(graph_iri)
        target.remove((None, None, None))
        for triple in graph:
            target.add(triple)

    async def create_dataset(self, name: str) -> None:
        self._enter("create_dataset", name)
        if name in self._datasets:
            raise Conflict(f"dataset {name} exists")
        self._datasets[name] = Dataset()

    async def drop_dataset(self, name: str) -> None:
        self._enter("drop_dataset", name)
        if name not in self._datasets:
            raise NotFound(f"no dataset {name}")
        del self._datasets[name]

    async def list_datasets(self) -> list[str]:
        self._enter("list_datasets", "")
        return list(self._datasets)
