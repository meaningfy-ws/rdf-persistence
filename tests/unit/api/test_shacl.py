"""SHACL validation: the parser lock is held where the shapes are not warmed up, and not after a warm-up."""

import shutil
import uuid
from pathlib import Path

import pytest
from rdflib import RDF, SH, Graph, Namespace

from rdf_persistence.api.services import shacl
from rdf_persistence.api.services.documents import Documents
from rdf_persistence.core.domain import sparql_parsing
from rdf_persistence.core.services.artifacts import CONTEXT_FILE, SHAPES_FILE
from rdf_persistence.schema.services.schema import load_schema
from tests.toy import GENERATED, TOY_SCHEMA
from tests.unit.builders import RecordingLock

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
    monkeypatch.setattr(sparql_parsing, "SPARQL_PARSER_LOCK", recording)  # X2
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

    monkeypatch.setattr(shacl, "validate", spying)  # X2
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


def folder_with_shapes(tmp_path: Path, name: str, shapes_text: str) -> Path:
    """A folder with the generated context and the given shapes: all ``Documents`` reads at build."""
    folder = tmp_path / name
    folder.mkdir()
    shutil.copy(GENERATED / CONTEXT_FILE, folder / CONTEXT_FILE)
    (folder / SHAPES_FILE).write_text(shapes_text, encoding="utf-8")
    return folder


def unique_copy_of_generated_shapes(tmp_path: Path, name: str) -> Path:
    """The generated shapes plus a trailing comment no other test has: a digest nothing warmed yet."""
    text = (GENERATED / SHAPES_FILE).read_text(encoding="utf-8")
    return folder_with_shapes(tmp_path, name, f"{text}\n# {uuid.uuid4()}\n")


def test_documents_warm_up_when_built_and_validate_without_the_lock(lock, tmp_path):
    first = unique_copy_of_generated_shapes(tmp_path, "first")
    documents = Documents(load_schema(TOY_SCHEMA), first)
    assert lock.taken >= 1, "building the documents warmed the new shapes up under the lock"
    taken = lock.taken
    Documents(load_schema(TOY_SCHEMA), first)
    assert lock.taken == taken, (
        "the same shapes are warmed once per process: no lock the second time"
    )
    Documents(load_schema(TOY_SCHEMA), unique_copy_of_generated_shapes(tmp_path, "second"))
    assert lock.taken > taken, "other shapes warm up again"
    taken = lock.taken
    conforms, _, _ = documents._check(Graph())
    assert conforms
    assert lock.taken == taken, "checking a body takes no lock"


def test_each_documents_has_its_own_shapes_even_for_same_size_rewrites_of_the_file(tmp_path):
    before = SHAPES.replace('"never"', '"nevah"')
    after = SHAPES.replace('"never"', '"nevee"')
    assert len(before) == len(after), "a rewrite of the same size"
    assert before != after
    first = Documents(load_schema(TOY_SCHEMA), folder_with_shapes(tmp_path, "before", before))
    second = Documents(load_schema(TOY_SCHEMA), folder_with_shapes(tmp_path, "after", after))
    again = Documents(load_schema(TOY_SCHEMA), folder_with_shapes(tmp_path, "again", before))
    messages = [
        {str(m) for m in documents.shapes.objects(None, SH.message)}
        for documents in (first, second, again)
    ]
    assert messages == [{"nevah"}, {"nevee"}, {"nevah"}], "each reads the file it was built from"
    assert first.shapes is not again.shapes, "the same shapes are not one shared graph"
    first.shapes.add((EX.extra, RDF.type, EX.Thing))
    assert (EX.extra, RDF.type, EX.Thing) not in again.shapes, (
        "adding to one graph leaves the others"
    )


def test_load_warm_shapes_warms_once_per_content(monkeypatch, tmp_path):
    marker = EX[f"marker-{uuid.uuid4()}"]  # a digest no other test in this process has warmed
    same = f"{SHAPES}\n<{marker}> a <urn:example:Marker> .\n"
    other_marker = EX[f"marker-{uuid.uuid4()}"]
    other = f"{SHAPES}\n<{other_marker}> a <urn:example:Marker> .\n"
    paths = []
    for name, text in (("one", same), ("two", same), ("three", other)):
        path = tmp_path / f"{name}.ttl"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    warmed: list[Graph] = []
    original = shacl.warm_up

    def spying(shapes: Graph) -> None:
        warmed.append(shapes)
        original(shapes)

    monkeypatch.setattr(shacl, "warm_up", spying)  # X2
    one, two, three = (shacl.load_warm_shapes(path) for path in paths)
    assert len(warmed) == 2, "same bytes warm once, other bytes warm again"
    assert (marker, RDF.type, EX.Marker) in one, "the graph holds the file's triples"
    assert (marker, RDF.type, EX.Marker) not in three, "other bytes, other shapes"
    one.add((EX.extra, RDF.type, EX.Thing))
    assert (EX.extra, RDF.type, EX.Thing) not in two, "adding to one leaves the other unchanged"
    assert one is not two, "each caller gets a graph of its own"
