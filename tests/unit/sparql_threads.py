"""Every place the toolkit lets rdflib parse SPARQL, called by several threads at once, in a fresh process.

Not collected as tests; ``test_sparql_parser_threads`` runs it with ``python -m``. pyparsing finds the arity
of each parse action of rdflib's SPARQL grammar on its first call, in a counter it shares between threads; two
threads in that first call overshoot the counter and the action fails for the rest of the process. So the race
shows only in a process that has not parsed yet: the test starts a new one each time.

Exit status 0 when no thread failed and a parse after them works; 1 otherwise, the failures on stderr.
"""

import asyncio
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from rdflib import RDF, Graph
from rdflib.namespace import Namespace
from rdflib.plugins.sparql import prepareQuery

from rdf_persistence.domain.sparql import checked_group
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.migration_runner import migrate_dataset
from rdf_persistence.testkit.fakes import FakeStore
from tests.unit.services.migration_helpers import (
    ISBN,
    LIB,
    OLD_ISBN,
    RP,
    chain_of,
    migration,
    rename,
)
from tests.unit.services.test_migrate_dataset import STAMPS, dataset, stamp

THREADS = 8
EX = Namespace("urn:example:")
_SPARQL_SHAPE = """
PREFIX ex: <urn:example:>
PREFIX sh: <http://www.w3.org/ns/shacl#>
ex:Shape a sh:NodeShape ; sh:targetClass ex:Thing ; sh:sparql [
    sh:message "no" ;
    sh:select "SELECT $this WHERE { $this <urn:example:never> ?x }" ] .
"""


def _store() -> None:
    async def work() -> None:
        store = FakeStore()
        await store.create_dataset("d")
        await store.update("d", 'INSERT DATA { GRAPH <urn:g> { <urn:s> <urn:p> "o" } }')
        await store.query("d", "SELECT ?s WHERE { GRAPH ?g { ?s ?p ?o } }")

    asyncio.run(work())


def _checked_group() -> None:
    checked_group("?s <urn:p> ?o", template=False)
    checked_group("<urn:s> <urn:p> ?o", template=True)


def _shapes() -> None:
    shapes = Graph().parse(data=_SPARQL_SHAPE, format="turtle")
    thing = Graph()
    thing.add((EX.a, RDF.type, EX.Thing))
    Documents._check(SimpleNamespace(shapes=shapes), thing)  # type: ignore[arg-type]


def _migration() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        lib = chain_of(
            root / "lib", LIB, migration(LIB, "1", "2", rename(OLD_ISBN, ISBN)), current="2"
        )
        data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
        migrate_dataset(data, [(RP, chain_of(root / "rp", RP, current="1")), (LIB, lib)], STAMPS)


def main() -> int:
    jobs = [_store, _checked_group, _shapes, _migration]
    barrier = threading.Barrier(THREADS)
    failures: list[str] = []

    def run(index: int) -> None:
        barrier.wait()
        for job in jobs[index % len(jobs) :] + jobs[: index % len(jobs)]:
            try:
                job()
            except Exception as error:  # noqa: BLE001 -- any failure of a job is the finding
                failures.append(f"{job.__name__}: {error!r}")

    threads = [threading.Thread(target=run, args=(i,)) for i in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    try:
        prepareQuery("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1")
    except Exception as error:  # noqa: BLE001 -- any failure of the parse is the finding
        failures.append(f"a parse after the threads: {error!r}")
    for failure in sorted(set(failures)):
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
