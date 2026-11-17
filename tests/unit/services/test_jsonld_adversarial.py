"""The one JSON-LD path, attacked (manual-revision-notes stage 2, task 2.2, PD-6)."""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from rdflib import URIRef

from rdf_persistence.services.jsonld import (
    NamedGraphRefused,
    RelativeIriRefused,
    RemoteContextRefused,
    triples_of,
)
from rdf_persistence.testkit import no_network  # noqa: F401  (fixture)

EX = "https://ex.org/"
P = "http://ex.org/p"
NO_FIXTURE_HEALTH = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])

RELATIVE = st.from_regex(r"[a-z][a-z0-9]{0,6}(/[a-z0-9]{1,6}){0,2}", fullmatch=True)
REMOTE = st.sampled_from(
    [
        "http://x.invalid/c",
        "https://x.invalid/c.jsonld",
        "file:///etc/hostname",
        "/etc/hostname",
        "context.jsonld",
        "../c",
        "//x.invalid/c",
        "ftp://x.invalid/c",
        "urn:x:c",
    ]
)
GRAPH_NAMES = st.sampled_from(["urn:g", "https://ex.org/g", "_:g", "mailto:a@b.c"])


def _relative_documents(ref: str) -> dict[str, dict]:
    return {
        "subject": {"@id": ref, P: "x"},
        "object": {"@id": EX + "a", P: {"@id": ref}},
        "type": {"@id": EX + "a", "@type": ref},
        "datatype": {"@id": EX + "a", P: {"@value": "1", "@type": ref}},
        "vocab": {"@context": {"@vocab": ref + "/"}, "@id": EX + "a", "name": "x"},
        "relative base": {"@context": {"@base": ref + "/"}, "@id": "a", P: "x"},
        "in a graph array": {"@graph": [{"@id": ref, P: "x"}]},
        "in a list": {"@id": EX + "a", P: {"@list": [{"@id": ref}]}},
        "reverse": {"@id": EX + "a", "@reverse": {P: {"@id": ref}}},
    }


@given(ref=RELATIVE, where=st.sampled_from(sorted(_relative_documents("a"))))
def test_a_relative_iri_with_no_base_is_refused_wherever_it_stands(ref: str, where: str) -> None:
    """Probe of PD-6 (error matrix: relative IRI, no @base): the triple is refused, never dropped."""
    with pytest.raises(RelativeIriRefused):
        triples_of(_relative_documents(ref)[where])


@given(
    url=REMOTE, where=st.sampled_from(["top", "array", "node", "graph array", "scoped", "import"])
)
@NO_FIXTURE_HEALTH
@pytest.mark.usefixtures("no_network")
def test_a_context_that_is_not_inline_is_refused_and_nothing_is_fetched(
    url: str, where: str
) -> None:
    """Probe of PD-6 (error matrix: remote, file or @import context); the blocked network would raise otherwise."""
    documents = {
        "top": {"@context": url, "@id": EX + "a", P: "x"},
        "array": {"@context": [{"p": P}, url], "@id": EX + "a"},
        "node": {"@id": EX + "a", P: {"@context": url, "@id": EX + "b"}},
        "graph array": {"@graph": [{"@context": url, "@id": EX + "a"}]},
        "scoped": {"@context": {"t": {"@id": P, "@context": url}}, "@id": EX + "a", "t": "x"},
        "import": {"@context": {"@import": url}, "@id": EX + "a"},
    }
    with pytest.raises(RemoteContextRefused):
        triples_of(documents[where])


@given(name=GRAPH_NAMES, shape=st.sampled_from(["top", "array", "nested", "alias", "with default"]))
def test_a_statement_in_a_named_graph_is_refused(name: str, shape: str) -> None:
    """Probe of PD-6 (error matrix: names a graph): however the graph is spelled, none is taken in part."""
    node = {"@id": EX + "a", P: "x"}
    documents = {
        "top": {"@id": name, "@graph": [node]},
        "array": [{"@id": name, "@graph": [node]}],
        "nested": {"@id": EX + "o", P: {"@graph": [node]}},
        "alias": {"@context": {"g": "@graph"}, "@id": name, "g": [node]},
        "with default": {"@id": name, P: "z", "@graph": [node]},
    }
    with pytest.raises(NamedGraphRefused):
        triples_of(documents[shape])


@pytest.mark.parametrize(
    "document",
    [
        {"@id": EX + "a b", P: "x"},
        {"@id": EX + "a", P: {"@id": EX + "a b"}},
        {"@id": EX + "a", "http://ex.org/p q": "x"},
        {"@id": EX + "a\nb", P: "x"},
    ],
    ids=["subject", "object", "predicate", "control character"],
)
def test_a_statement_with_an_invalid_iri_is_not_dropped_in_silence(document: dict) -> None:
    """found T-5: PyLD drops a triple whose IRI has a space or a control character, as it did a relative one.

    The relative case is refused (PD-6) but this is the same silent loss. Expected a refusal (any
    exception) or one triple; actual an empty graph.
    """
    try:
        graph = triples_of(document)
    except Exception:  # noqa: BLE001  (any refusal is what is asked for)
        return
    assert len(graph) == 1, "the statement was lost without a word"


@pytest.mark.parametrize("document", [123, True, 1.5], ids=repr)
def test_a_scalar_document_is_not_an_empty_graph(document: object) -> None:
    """found T-6: a top-level JSON number or boolean is read as a document with no statements.

    Expected a refusal; actual an empty graph (a loaded file ``123`` would create an empty graph).
    """
    with pytest.raises(Exception):  # noqa: B017  (which one is the caller's mapping)
        triples_of(document)  # type: ignore[arg-type]


def test_a_null_base_leaves_a_relative_iri_that_is_refused() -> None:
    """found T-1: ``"@base": null`` removes the document's base, so ``@id: "a"`` is relative and dropped.

    Input ``{"@context": {"@base": null}, "@id": "a", p: "x"}``; expected RelativeIriRefused;
    actual an empty graph, the very silent drop PD-6 exists to end.
    """
    with pytest.raises(RelativeIriRefused):
        triples_of({"@context": {"@base": None}, "@id": "a", P: "x"})


@given(
    iri=st.sampled_from(
        [
            "urn:isbn:123",
            "mailto:a@b.c",
            "tag:x,2020:y",
            "did:example:123",
            "ftp://h/p",
            "urn:uuid:6f1c0c9e-0000-4000-8000-000000000001",
            "https://other.org/no-base.invalid/x",
            "https://sub.no-base.invalid/x",
            "http://no-base.invalid.example/x",
        ]
    )
)
def test_an_absolute_iri_of_any_scheme_is_kept_even_if_it_mentions_the_stand_in_host(
    iri: str,
) -> None:
    """Probe of PD-6: only an IRI that *starts* with the stand-in base counts as relative."""
    graph = triples_of({"@id": iri, P: {"@id": iri}})
    assert (URIRef(iri), URIRef(P), URIRef(iri)) in graph, f"{iri!r} was kept as it is"


def test_a_big_document_is_read_in_bounded_time() -> None:
    """Probe of PD-6: 5 000 nodes."""
    nodes = [{"@id": f"{EX}{i}", P: "x"} for i in range(5_000)]
    assert len(triples_of(nodes)) == 5_000, "every node was read"
