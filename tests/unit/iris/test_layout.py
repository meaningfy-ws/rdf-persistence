"""The fixed IRI and name layout of the iris domain (PD-4, PD-6a): policy-free, and free of the services."""

import ast
from pathlib import Path

import pytest
from rdflib import BNode, Literal, URIRef

from rdf_persistence.core.domain.exceptions import InvalidIri
from rdf_persistence.iris.domain import layout
from rdf_persistence.iris.domain.layout import (
    application_database_name,
    graph_iri,
    is_canonical_uuid,
    is_inside_tenant,
    is_skolem_of,
    root_of_graph,
    skolem_iri,
    system_database_name,
    tenant_name_prefix,
    toolkit_principal_iri,
)

BASE = "https://example.org/library/"
TENANT = URIRef(f"{BASE}libraries/12345678-1234-4234-8234-123456789abc")
UUID_A = "12345678-1234-4234-8234-123456789abc"

LAYOUT_FUNCTIONS = (
    "graph_iri",
    "root_of_graph",
    "skolem_iri",
    "is_skolem_of",
    "toolkit_principal_iri",
    "policy_record_iri",
    "stamps_graph_iri",
    "is_inside_tenant",
    "is_canonical_uuid",
    "system_database_name",
    "application_database_name",
    "tenant_name_prefix",
)
_SOURCE = Path(layout.__file__).read_text()
_IMPORTED_MODULES = [
    alias.name
    for node in ast.walk(ast.parse(_SOURCE))
    if isinstance(node, ast.Import)
    for alias in node.names
] + [node.module or "" for node in ast.walk(ast.parse(_SOURCE)) if isinstance(node, ast.ImportFrom)]


def test_the_layout_module_defines_the_twelve_policy_free_functions():  # TC-30
    defined = {node.name for node in ast.parse(_SOURCE).body if isinstance(node, ast.FunctionDef)}
    assert set(LAYOUT_FUNCTIONS) <= defined, "each layout function is defined in iris.domain.layout"


def test_the_layout_module_is_the_one_of_the_iris_theme():  # TC-30
    assert layout.__name__ == "rdf_persistence.iris.domain.layout", "the module stands in the theme"


def test_the_layout_module_imports_only_the_core_domain_of_the_toolkit():  # TC-30
    toolkit = [name for name in _IMPORTED_MODULES if name.split(".")[0] == "rdf_persistence"]
    outside = [name for name in toolkit if not name.startswith("rdf_persistence.core.domain")]
    assert outside == [], f"iris.domain.layout imports outside core.domain: {outside}"


def test_the_layout_module_imports_no_generated_package():
    generated = [name for name in _IMPORTED_MODULES if "generated" in name.split(".")]
    assert generated == [], f"iris.domain.layout imports a generated package: {generated}"


def test_graph_iri_appends_graph():
    root = f"{BASE}libraries/t/books/b"
    assert graph_iri(root) == URIRef(f"{root}/graph"), "a graph IRI is its root plus slash graph"
    assert graph_iri(root) != URIRef(root), "never the root IRI itself"


def test_root_of_graph_is_the_inverse_of_graph_iri():
    root = f"{BASE}libraries/t/books/b"
    assert root_of_graph(graph_iri(root)) == URIRef(root), (
        "the root of a graph IRI is the root it was made from"
    )


@pytest.mark.parametrize(
    "iri", [f"{BASE}libraries/t/books/b", f"{BASE}libraries/t/books/b/graphs", "/graph"]
)
def test_root_of_graph_refuses_what_is_not_a_graph_iri(iri):
    with pytest.raises(InvalidIri):
        root_of_graph(URIRef(iri))


@pytest.mark.parametrize("prefix", ["", "Lib", "a" * 21, "li b", "lib_x", "-lib"])
def test_a_prefix_outside_pd_6a_is_refused(prefix):
    with pytest.raises(InvalidIri, match="prefix"):
        system_database_name(prefix)
    with pytest.raises(InvalidIri, match="prefix"):
        tenant_name_prefix(prefix)


@pytest.mark.parametrize("prefix", ["a", "a" * 20, "a1b2"])
def test_a_prefix_inside_pd_6a_gives_the_known_database_names(prefix):
    """Probe of PD-6a: the 20-character prefix is the longest one accepted, by all three functions."""
    assert system_database_name(prefix) == f"{prefix}-system"
    assert application_database_name(prefix) == f"{prefix}-app"
    assert tenant_name_prefix(prefix) == f"{prefix}-t-"


def test_a_skolem_iri_lives_under_its_graph_and_is_fresh_each_time():
    graph = graph_iri(f"{TENANT}/books/1")
    first = skolem_iri(graph)
    assert first.startswith(f"{graph}/.well-known/genid/"), "under the graph, in the genid space"
    assert skolem_iri(graph) != first, "each mint is fresh"


def test_is_skolem_of_tells_the_skolem_iris_of_a_graph_from_everything_else():
    graph = graph_iri(f"{TENANT}/books/1")
    other = graph_iri(f"{TENANT}/books/2")
    assert is_skolem_of(graph, skolem_iri(graph)), "a minted skolem IRI"
    assert not is_skolem_of(graph, skolem_iri(other)), "a skolem IRI of another graph"
    assert not is_skolem_of(graph, graph), "the graph IRI itself"
    assert not is_skolem_of(graph, BNode("x")), "a blank node"
    assert not is_skolem_of(graph, Literal(f"{graph}/.well-known/genid/x")), "a literal"


def test_the_toolkit_principal_is_toolkit_under_the_base():
    assert toolkit_principal_iri(BASE) == URIRef(f"{BASE}toolkit"), (
        "the toolkit principal is toolkit under the base"
    )


@pytest.mark.parametrize(
    ("iri", "inside"),
    [
        (f"{TENANT}/books/1", True),
        (f"{TENANT}/access", True),
        (str(TENANT), False),  # the tenant itself is not inside itself
        (f"{TENANT}x/books/1", False),  # a longer sibling
        ("https://example.org/other/books/1", False),
    ],
)
def test_an_iri_is_inside_a_tenant_only_below_its_path(iri, inside):
    assert is_inside_tenant(str(TENANT), iri) is inside, iri


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        (UUID_A, True),
        (UUID_A.upper(), False),
        (UUID_A.replace("-", ""), False),
        ("books", False),
        ("", False),
    ],
)
def test_only_a_lower_case_hyphenated_uuid_is_canonical(text, canonical):
    assert is_canonical_uuid(text) is canonical, "only a lower-case hyphenated uuid is canonical"
