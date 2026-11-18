"""SHACL validation: the parser lock is held where the shapes are not warmed up, and not after a warm-up."""

import pytest
from rdflib import RDF, Graph, Namespace

from rdf_persistence.core.domain import sparql_parsing
from rdf_persistence.services import shacl
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from tests.toy import TOY_SCHEMA
from tests.unit.core.test_sparql_parsing import RecordingLock
from tests.unit.services.conftest import GENERATED

EX = Namespace("urn:example:")
SHAPES = """
@prefix ex: <urn:example:> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
ex:Shape a sh:NodeShape ; sh:targetClass ex:Thing ; sh:closed true ; sh:ignoredProperties ( <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ) ;
    sh:property [ sh:path ex:name ; sh:minCount 1 ] ;
    sh:sparql [ sh:message "never" ; sh:select "SELECT $this WHERE { $this <urn:example:never> ?x }" ] .
"""


@pytest.fixture
def lock(monkeypatch: pytest.MonkeyPatch) -> RecordingLock:
    recording = RecordingLock()
    monkeypatch.setattr(sparql_parsing, "SPARQL_PARSER_LOCK", recording)
    return recording


@pytest.fixture
def shapes() -> Graph:
    return Graph().parse(data=SHAPES, format="turtle")


def thing(*, named: bool) -> Graph:
    graph = Graph()
    graph.add((EX.a, RDF.type, EX.Thing))
    if named:
        graph.add((EX.a, EX.name, EX.n))
    return graph


def copy_of(shapes: Graph) -> Graph:
    scratch = Graph()
    scratch += shapes
    return scratch


def test_validate_locked_holds_the_lock_for_the_whole_validation(monkeypatch, lock, shapes):
    depths: list[int] = []
    original = shacl.validate

    def spying(*args, **kwargs):
        depths.append(lock.depth)
        return original(*args, **kwargs)

    monkeypatch.setattr(shacl, "validate", spying)
    conforms, _, _ = shacl.validate_locked(thing(named=True), copy_of(shapes))
    assert depths == [1], "pyshacl ran with the lock held"
    assert lock.depth == 0
    assert conforms


def test_warm_up_runs_one_validation_under_the_lock(lock, shapes):
    shacl.warm_up(shapes)
    assert lock.taken == 1
    assert not list(shapes.subjects(RDF.type, EX.Thing)), "the shapes graph is not written to"


def test_a_validation_after_the_warm_up_does_not_take_the_lock(lock, shapes):
    shacl.warm_up(shapes)
    taken = lock.taken
    conforms, report, _ = shacl.validate_warm(thing(named=False), copy_of(shapes))
    assert lock.taken == taken, "no lock after the warm-up"
    assert not conforms, "and it still validates: the shape wants a name"
    assert len(report) > 0


def test_documents_warm_up_when_built_and_validate_without_the_lock(lock):
    documents = Documents(load_schema(TOY_SCHEMA), GENERATED)
    assert lock.taken >= 1, "building the documents warmed the shapes up under the lock"
    taken = lock.taken
    conforms, _, _ = documents._check(Graph())
    assert conforms
    assert lock.taken == taken, "checking a body takes no lock"
