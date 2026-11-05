"""The generated shapes validate instances as the specs say (rp-metamodel, PD-7, PD-24)."""

from dataclasses import dataclass
from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SH

from rdf_persistence.generation.extensions.shacl import render_shapes

METAMODEL = Path(__file__).parents[3] / "rdf_persistence" / "model" / "rp.yaml"

PREFIXES = """
@prefix lib: <https://example.org/ns/library#> .
@prefix bibo: <http://purl.org/ontology/bibo/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix odrl: <http://www.w3.org/ns/odrl/2/> .
@prefix rp: <https://meaningfy.ws/ns/rdf-persistence#> .
@prefix ex: <https://example.org/data/> .
"""
SKOS_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
DCTERMS = "http://purl.org/dc/terms/"
RP = "https://meaningfy.ws/ns/rdf-persistence#"
SPARQL_COMPONENT = SH.SPARQLConstraintComponent
XONE_COMPONENT = SH.XoneConstraintComponent
CLOSED_COMPONENT = SH.ClosedConstraintComponent

DATABASE = "acme-t-" + "0" * 32


@dataclass(frozen=True)
class Verdict:
    """What a validation said: whether the data conforms, and the paths and components it names."""

    conforms: bool
    paths: frozenset[str]
    components: frozenset[URIRef]


@dataclass(frozen=True)
class Case:
    name: str
    data: str
    conforms: bool
    path: str | None = None
    component: URIRef | None = None


def book(*, label: str | None = "A book", body: str = "") -> str:
    label_triple = f'skos:prefLabel "{label}" ;' if label is not None else ""
    return f"""
    ex:book a bibo:Book ; {label_triple} dcterms:description "About a book" ; {body} .
    """


def chapter(*, extra: str = "") -> str:
    return f"""
    ex:book a bibo:Book ; skos:prefLabel "A book" ; dcterms:description "About" ; lib:chapter ex:ch1 .
    ex:ch1 a bibo:Chapter ; bibo:chapter 1 {extra} .
    """


def grant(
    *, role: str | None = "editor", action: str | None = None, assignee: str = "ex:alice"
) -> str:
    role_triple = f'rp:role "{role}" ;' if role else ""
    action_triple = f"odrl:action {action} ;" if action else ""
    return f"""[ a odrl:Permission ; odrl:assignee {assignee} ; odrl:target ex:tenant ;
                  {role_triple} {action_triple} ]"""


def access(*grants: str, state: str = "rp:Active", kind: str = "rp:TenantAccess") -> str:
    listed = " , ".join(grants)
    grants_triple = f"rp:grant {listed} ;" if grants else ""
    return f"""
    ex:tenant a {kind} ; skos:prefLabel "Acme" ; rp:state {state} ;
        rp:databaseName "{DATABASE}" ; {grants_triple} dcterms:description "The record" .
    """


def verdict(shapes: Graph, data: str) -> Verdict:
    data_graph = Graph().parse(data=PREFIXES + data, format="turtle")
    conforms, report, _ = validate(data_graph, shacl_graph=shapes, inference="none")
    results = list(report.subjects(RDF.type, SH.ValidationResult))
    return Verdict(
        conforms,
        frozenset(str(p) for r in results for p in report.objects(r, SH.resultPath)),
        frozenset(c for r in results for c in report.objects(r, SH.sourceConstraintComponent)),
    )


@pytest.fixture(scope="session")
def toy_shapes(generated_toy: Path) -> Graph:
    return Graph().parse(generated_toy / "shapes.ttl")


@pytest.fixture(scope="session")
def metamodel_shapes(tmp_path_factory: pytest.TempPathFactory) -> Graph:
    folder = tmp_path_factory.mktemp("metamodel")
    shapes = render_shapes(METAMODEL)
    (folder / shapes.name).write_text(shapes.text, encoding="utf-8")
    return Graph().parse(folder / shapes.name)


LIBRARY_ACCESS_CASES = [
    Case(
        "a library access record with one librarian grant",
        access(grant(role="librarian"), kind="lib:LibraryAccess"),
        True,
    ),
]


@pytest.mark.parametrize("case", LIBRARY_ACCESS_CASES, ids=lambda case: case.name)
def test_the_toy_shapes_judge_the_library_access_record(toy_shapes: Graph, case: Case) -> None:
    result = verdict(toy_shapes, case.data)
    assert result.conforms is case.conforms, f"{case.name}: conforms is {result.conforms}"


BOOK_CASES = [
    Case("a book with a label", book(), True),
    Case("a book without a label", book(label=None), False, path=SKOS_LABEL),
    Case("a chapter without a label", chapter(), True),
    Case(
        "a chapter with a bookkeeping version",
        chapter(extra="; rp:version 'v1' ; dcterms:modified '2026-11-05T10:00:00Z'"),
        True,
    ),
    Case(
        "a chapter with a bookkeeping creator and contributor",
        chapter(
            extra="; dcterms:created '2026-11-05T09:00:00Z' ; dcterms:creator ex:alice ; dcterms:contributor ex:bob"
        ),
        True,
    ),
    Case(
        "a chapter with an unknown predicate",
        chapter(extra="; lib:unknown 'x'"),
        False,
        component=CLOSED_COMPONENT,
    ),
    Case(
        "a scan of a book that is not in the graph",
        """ex:scan a lib:Scan ; skos:prefLabel "S" ; dcterms:description "D" ;
              <http://schema.org/exampleOfWork> ex:elsewhere .""",
        True,
    ),
]


@pytest.mark.parametrize("case", BOOK_CASES, ids=lambda case: case.name)
def test_the_toy_shapes_judge_the_instance(toy_shapes: Graph, case: Case) -> None:
    result = verdict(toy_shapes, case.data)
    assert result.conforms is case.conforms, f"{case.name}: conforms is {result.conforms}"
    if case.path:
        assert case.path in result.paths, f"{case.name}: the report must name {case.path}"
    if case.component:
        assert case.component in result.components, (
            f"{case.name}: the report must name {case.component}"
        )


ACCESS_CASES = [
    Case("an access record with one role grant", access(grant()), True),
    Case("an access record without grants", access(), True),
    Case(
        "a grant with a role and an action",
        access(grant(role="editor", action="odrl:read")),
        False,
        component=XONE_COMPONENT,
    ),
    Case("a grant with neither", access(grant(role=None)), False, component=XONE_COMPONENT),
    Case("a direct grant with an action", access(grant(role=None, action="odrl:read")), True),
    Case(
        "two equal grants",
        access(grant(), grant()),
        False,
        component=SPARQL_COMPONENT,
    ),
    Case(
        "two direct grants, equal with the role absent in both",
        access(grant(role=None, action="odrl:read"), grant(role=None, action="odrl:read")),
        False,
        component=SPARQL_COMPONENT,
    ),
    Case(
        "grants that differ in the role", access(grant(role="editor"), grant(role="reader")), True
    ),
    Case(
        "grants that differ in the assignee",
        access(grant(), grant(assignee="ex:bob")),
        True,
    ),
    Case(
        "a grant by role and a grant by action",
        access(grant(), grant(role=None, action="odrl:read")),
        True,
    ),
]


@pytest.mark.parametrize("case", ACCESS_CASES, ids=lambda case: case.name)
def test_the_metamodel_shapes_judge_the_access_record(metamodel_shapes: Graph, case: Case) -> None:
    result = verdict(metamodel_shapes, case.data)
    assert result.conforms is case.conforms, f"{case.name}: conforms is {result.conforms}"
    if case.component:
        assert case.component in result.components, (
            f"{case.name}: the report must name {case.component}"
        )
