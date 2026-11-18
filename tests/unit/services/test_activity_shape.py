"""The stored shape of an activity and its round trip through RDF, JSON-LD and the model (message-bus PD-3, PD-4, RISK-7)."""

from datetime import UTC, datetime, timedelta
from functools import cache

import pytest
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import PROV

from rdf_persistence.core.domain.generated.rp_provenance import (
    Activity,
    Add,
    Generation,
    Invalidation,
    Remove,
    Replace,
)
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.provenance import activity_triples
from rdf_persistence.testkit import assert_isomorphic
from rdf_persistence_generation.testkit.conformance import Conformance
from rdf_persistence_generation.testkit.roundtrip import without_framing
from tests.toy import ADA, BOB, TENANT, TOY_SCHEMA, book_iri, toy_mapper

RP = "https://meaningfy.ws/ns/rdf-persistence#"
BOOK_CLASS = "https://example.org/ns/library#Book"
A = "urn:uuid:7a1e1d6e-2f0b-4c57-9a52-2f2f5d1f6a10"
STARTED = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
ENDED = STARTED + timedelta(seconds=2)
PROVENANCE_GRAPH = URIRef(f"{TENANT}/provenance")
ACTIVITY_TYPES = [URIRef(f"{RP}Replace"), PROV.Activity]


@cache
def toy() -> Conformance:
    return Conformance.of(TOY_SCHEMA)


def part[P: (Generation, Invalidation)](
    kind: type[P], n: int, version: str, *, entity_class: str | None = BOOK_CLASS
) -> P:
    return kind(
        activity=A,
        at_time=ENDED,
        entity=book_iri(n),
        entity_class=entity_class,
        entity_version=version,
    )


def activity[M: Activity](cls: type[M], **slots) -> M:
    return cls(
        id=A,
        was_associated_with=[ADA, BOB],
        started_at_time=STARTED,
        ended_at_time=ENDED,
        **slots,
    )


def types_of(cls: type[Activity]) -> list[URIRef]:
    own = [] if cls is Activity else [URIRef(f"{RP}{cls.__name__}")]
    return [*own, PROV.Activity]


CASES = {
    "replace": activity(
        Replace,
        generations=[part(Generation, 1, "new")],
        invalidations=[part(Invalidation, 1, "old")],
    ),
    "add": activity(Add, generations=[part(Generation, 2, "first")]),
    "remove": activity(Remove, invalidations=[part(Invalidation, 3, "last")]),
    "bare": activity(
        Activity,
        generations=[part(Generation, 4, "g4"), part(Generation, 5, "g5")],
        invalidations=[part(Invalidation, 6, "i6")],
    ),
    "no_entity_class": activity(Add, generations=[part(Generation, 7, "g7", entity_class=None)]),
}
EVERY_ACTIVITY = pytest.mark.parametrize("model", CASES.values(), ids=CASES.keys())


def expected_graph(model: Activity, types: list[URIRef]) -> Graph:
    """The Turtle of design.md PD-3 for ``model``, the parts as blank nodes."""
    a = f"<{model.id}>"
    parts = [("rp:generation", "prov:Generation", p) for p in model.generations or []] + [
        ("rp:invalidation", "prov:Invalidation", p) for p in model.invalidations or []
    ]
    lines = [
        "@prefix rp: <https://meaningfy.ws/ns/rdf-persistence#> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        f"{a} a {', '.join(f'<{t}>' for t in types)} ;",
        f'  prov:startedAtTime "{model.started_at_time.isoformat()}"^^xsd:dateTime ;',  # type: ignore[union-attr]
        f'  prov:endedAtTime "{model.ended_at_time.isoformat()}"^^xsd:dateTime ;',  # type: ignore[union-attr]
        *(f"  prov:wasAssociatedWith <{who}> ;" for who in model.was_associated_with or []),
        *(f"  {link} _:p{n} ;" for n, (link, _, _) in enumerate(parts)),
        "  .",
    ]
    for n, (_, kind, p) in enumerate(parts):
        lines += [
            f"_:p{n} a {kind} ; prov:activity {a} ;",
            f'  prov:atTime "{p.at_time.isoformat()}"^^xsd:dateTime ;',
            f"  rp:entity <{p.entity}> ;",
            *([f"  rp:entityClass <{p.entity_class}> ;"] if p.entity_class else []),
            f'  rp:entityVersion "{p.entity_version}" .',
        ]
    return Graph().parse(data="\n".join(lines), format="turtle")


def stored(model: Activity) -> Graph:
    graph = Graph()
    for triple in activity_triples(model, types_of(type(model))):
        graph.add(triple)
    return graph


def mapped(model: Activity) -> Graph:
    """The mapper's graph: the activity's own class only, without the ancestor types the session adds (TC-11)."""
    return toy_mapper().to_graph(model)


def unordered[M: Activity](model: M) -> M:
    """``model`` with its parts in the order of ``(entity, entity_version)``: RDF keeps no order (PD-4)."""

    def order(parts):
        return sorted(parts, key=lambda p: (p.entity, p.entity_version)) if parts else parts

    return model.model_copy(
        update={
            "generations": order(model.generations),
            "invalidations": order(model.invalidations),
            "was_associated_with": sorted(model.was_associated_with or []) or None,
        }
    )


def without_ancestor_type(model: Activity, graph: Graph) -> Graph:
    """``graph`` as the session writes it, minus the ``prov:Activity`` type the mapper does not write."""
    trimmed = Graph()
    for s, p, o in graph:
        if (p, o) != (RDF.type, PROV.Activity) or type(model) is Activity:
            trimmed.add((s, p, o))
    return trimmed


@EVERY_ACTIVITY
def test_tc10_the_triples_of_an_activity_are_the_pd3_shape(model: Activity) -> None:
    assert_isomorphic(expected_graph(model, types_of(type(model))), stored(model))


@EVERY_ACTIVITY
def test_tc11_the_mapper_writes_the_same_graph_but_the_ancestor_type(model: Activity) -> None:
    assert_isomorphic(without_ancestor_type(model, stored(model)), mapped(model))


@EVERY_ACTIVITY
def test_tc12_the_json_of_the_model_expands_to_the_mapped_graph(model: Activity) -> None:
    graph = toy().graph_of(model, type(model).__name__)
    assert_isomorphic(mapped(model), graph)


def framed(model: Activity) -> dict:
    name = type(model).__name__
    body = without_framing(toy().documents.frame(mapped(model), toy().view.get_class(name)))
    assert isinstance(body, dict), "one activity is one object"
    return body


def with_class_iris_expanded(body: dict) -> dict:
    """``body`` with the compact IRI of each ``entity_class`` written out, with the context's prefixes.

    Compaction writes a value of an ``@id`` term as ``lib:Book`` when the context has the prefix ``lib``.
    """
    prefixes = toy().documents.context
    parts = ("generations", "invalidations")

    def expanded(part: dict) -> dict:
        prefix, _, rest = part.get("entity_class", "").partition(":")
        if prefix not in prefixes or not rest:
            return part
        return {**part, "entity_class": f"{prefixes[prefix]}{rest}"}

    return {**body, **{p: [expanded(x) for x in body[p]] for p in parts if p in body}}


@EVERY_ACTIVITY
def test_tc13_the_framed_graph_compacts_to_the_model_once_compact_iris_are_expanded(
    model: Activity,
) -> None:
    back = type(model).model_validate(with_class_iris_expanded(framed(model)))
    assert unordered(back) == unordered(model), "the framed graph reads back as the model"


@EVERY_ACTIVITY
def test_tc14_the_mapper_reads_the_stored_graph_and_ignores_the_ancestor_type(
    model: Activity,
) -> None:
    back = toy_mapper().from_graph(type(model), model.id, stored(model), PROVENANCE_GRAPH)
    assert unordered(back) == unordered(model), "the mapper reads back the model"


def test_tc17_a_generation_without_an_entity_class_has_no_such_triple() -> None:
    graph = stored(CASES["no_entity_class"])
    assert list(graph.triples((None, URIRef(f"{RP}entityClass"), None))) == [], "no entityClass"


def test_the_vocabulary_names_the_pd3_terms() -> None:
    assert {
        str(t)
        for t in (
            v.ACTIVITY_STARTED,
            v.ACTIVITY_ENDED,
            v.ASSOCIATED_WITH,
            v.HAS_GENERATION,
            v.HAS_INVALIDATION,
            v.PART_ACTIVITY,
            v.AT_TIME,
            v.ENTITY,
            v.ENTITY_CLASS,
            v.ENTITY_VERSION,
            v.GENERATION,
            v.INVALIDATION,
        )
    } == {
        str(PROV.startedAtTime),
        str(PROV.endedAtTime),
        str(PROV.wasAssociatedWith),
        f"{RP}generation",
        f"{RP}invalidation",
        str(PROV.activity),
        str(PROV.atTime),
        f"{RP}entity",
        f"{RP}entityClass",
        f"{RP}entityVersion",
        str(PROV.Generation),
        str(PROV.Invalidation),
    }, "each constant is the IRI of PD-3"


@pytest.mark.parametrize("missing", ["started_at_time", "ended_at_time"])
def test_an_activity_without_a_start_or_an_end_time_is_refused_naming_its_id(missing: str) -> None:
    incomplete = CASES["add"].model_copy(update={missing: None})
    with pytest.raises(ValueError, match=A):
        activity_triples(incomplete, types_of(Add))
