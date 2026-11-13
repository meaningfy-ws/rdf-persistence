"""The tenant id rewrite and the policies it cannot handle (tenant-dump-restore PD-4, TC-04 to TC-09)."""

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS

from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.tenant_dump import glued_templates, rewrite
from tests.toy import SETTINGS, TOY_SCHEMA

OLD = "9f1e6c2a-3b4d-4e5f-8a9b-0c1d2e3f4a5b"
NEW = "4c2b7d9e-1a2b-4c3d-9e4f-5a6b7c8d9e0f"
BOOK = "book"
USERS = "users"


def quads_of(dataset: Dataset) -> set[tuple]:
    return {(s, p, o, g) for s, p, o, g in dataset.quads()}


def dataset_of(*quads: tuple) -> Dataset:
    dataset = Dataset()
    for subject, predicate, obj, graph in quads:
        dataset.add((subject, predicate, obj, graph))
    return dataset


def swap(iri: str, old: str = OLD, new: str = NEW) -> URIRef:
    """The expected IRI: the tenant id spelled out, never a regex, so the test does not mirror the code."""
    return URIRef(iri.replace(old, new))


def iris_of(settings: ServiceSettings = SETTINGS) -> Iris:
    return Iris(settings, *iri_types(load_schema(TOY_SCHEMA)))


def policy_settings(**templates: str) -> ServiceSettings:
    return SETTINGS.model_copy(update={"iri_policy": IriPolicy(**templates)})


# -- TC-04: the worked example of the design ---------------------------------------------------


def test_the_six_terms_of_the_worked_example_are_rewritten_or_kept():
    iris = iris_of()
    base = SETTINGS.base
    tenant = str(iris.tenant(OLD))
    aggregate = str(iris.mint_aggregate(tenant, BOOK, "books"))
    genid = URIRef(f"{aggregate}/graph/.well-known/genid/77ab")
    users = str(iris.mint_aggregate(tenant, BOOK, USERS))
    root, graph = URIRef(tenant), URIRef(f"{aggregate}/graph")
    literal = Literal(f"see {tenant}")
    source = dataset_of(
        (root, DCTERMS.title, literal, iris.meta(tenant)),
        (URIRef(aggregate), DCTERMS.relation, genid, graph),
        (URIRef(users), DCTERMS.relation, URIRef(users), URIRef(f"{users}/graph")),
    )
    result = quads_of(rewrite(source, base, OLD, NEW))
    assert result == {
        (swap(tenant), DCTERMS.title, literal, swap(str(iris.meta(tenant)))),
        (swap(aggregate), DCTERMS.relation, swap(str(genid)), swap(str(graph))),
        (swap(users), DCTERMS.relation, swap(users), swap(f"{users}/graph")),
    }
    assert str(genid) != str(swap(str(genid)))  # the genid IRI did move, only its tail stayed


def test_a_predicate_a_datatype_and_a_blank_node_are_untouched():
    tenant = str(iris_of().tenant(OLD))
    predicate = URIRef(f"{tenant}/predicate")
    typed = Literal("x", datatype=URIRef(f"{tenant}/datatype"))
    graph = URIRef(f"{tenant}/meta")
    source = dataset_of((URIRef(tenant), predicate, typed, graph))
    ((subject, pred, obj, _),) = quads_of(rewrite(source, SETTINGS.base, OLD, NEW))
    assert (subject, pred, obj) == (swap(tenant), predicate, typed)


# -- TC-05: the flat policy --------------------------------------------------------------------

FLAT = "{base}{tenant_id}/{type}/{id}"
FLAT_OLD, FLAT_NEW = "p4x8k2m", "q5y9l3n"


def flat_settings() -> ServiceSettings:
    return SETTINGS.model_copy(
        update={
            "base": "http://mwb.meaningfy.ws/",
            "iri_policy": IriPolicy(
                tenant_template="{base}project/{tenant_id}",
                aggregate_template=FLAT,
                part_template=FLAT,
                loaded_graph_template=FLAT,
                tenant_id=IdSpec(kind=IdKind.RANDOM, length=7),
                object_id=IdSpec(kind=IdKind.RANDOM, length=13),
            ),
        }
    )


def test_under_the_flat_policy_the_aggregate_part_and_loaded_graph_take_the_new_id():
    iris = iris_of(flat_settings())
    tenant = str(iris.tenant(FLAT_OLD))
    aggregate = str(iris.mint_aggregate(tenant, BOOK, "books"))
    part = str(iris.mint_part(tenant, aggregate, sorted(iris.owned_types)[0]))
    loaded = str(iris.mint_loaded_graph(tenant, aggregate))
    source = dataset_of(
        (URIRef(aggregate), DCTERMS.hasPart, URIRef(part), URIRef(f"{aggregate}/graph")),
        (URIRef(part), DCTERMS.title, Literal("t"), URIRef(loaded)),
    )
    result = quads_of(rewrite(source, iris.settings.base, FLAT_OLD, FLAT_NEW))
    new_tenant = str(iris.tenant(FLAT_NEW))
    new_aggregate, new_part, new_loaded = (
        swap(i, FLAT_OLD, FLAT_NEW) for i in (aggregate, part, loaded)
    )
    assert result == {
        (new_aggregate, DCTERMS.hasPart, new_part, URIRef(f"{new_aggregate}/graph")),
        (new_part, DCTERMS.title, Literal("t"), new_loaded),
    }
    assert iris.is_aggregate_graph(new_tenant, f"{new_aggregate}/graph")
    assert iris.is_loaded_graph(new_tenant, str(new_loaded))


# -- TC-06: another base ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "foreign",
    [f"https://other.org/libraries/{OLD}", f"https://example.org/library-extra/{OLD}"],
)
def test_an_iri_outside_the_base_holding_the_old_id_is_unchanged(foreign: str):
    source = dataset_of((URIRef(foreign), DCTERMS.relation, URIRef(foreign), URIRef(foreign)))
    assert quads_of(rewrite(source, SETTINGS.base, OLD, NEW)) == quads_of(source)


# -- TC-07: the id next to - or ., and glued to letters ---------------------------------------


def test_an_id_next_to_a_dash_or_a_dot_is_rewritten_and_the_policy_accepts_the_result():
    settings = policy_settings(
        aggregate_template="{base}{tenant_id}-{id}", meta_template="{tenant}.meta"
    )
    iris = iris_of(settings)
    aggregate = str(iris.mint_aggregate(str(iris.tenant(OLD)), BOOK, "books"))
    meta = str(iris.meta(str(iris.tenant(OLD))))
    source = dataset_of((URIRef(aggregate), DCTERMS.relation, URIRef(aggregate), URIRef(meta)))
    ((subject, _, obj, graph),) = quads_of(rewrite(source, SETTINGS.base, OLD, NEW))
    new_tenant = str(iris.tenant(NEW))
    assert (subject, obj) == (swap(aggregate),) * 2
    assert graph == iris.meta(new_tenant)
    assert iris.is_aggregate(new_tenant, str(subject))


@pytest.mark.parametrize(
    "glued", [f"{SETTINGS.base}x{OLD}", f"{SETTINGS.base}{OLD}x", f"{SETTINGS.base}x{OLD}x"]
)
def test_an_id_glued_to_a_letter_or_digit_is_unchanged(glued: str):
    source = dataset_of((URIRef(glued), DCTERMS.relation, URIRef(glued), URIRef(glued)))
    assert quads_of(rewrite(source, SETTINGS.base, OLD, NEW)) == quads_of(source)


# -- TC-08: a tenant aggregate under the `users` path -----------------------------------------


def test_an_aggregate_under_the_users_path_moves_as_graph_subject_and_object():
    iris = iris_of()
    users = str(iris.mint_aggregate(str(iris.tenant(OLD)), BOOK, USERS))
    graph = f"{users}/graph"
    source = dataset_of((URIRef(users), DCTERMS.relation, URIRef(users), URIRef(graph)))
    ((subject, _, obj, moved),) = quads_of(rewrite(source, SETTINGS.base, OLD, NEW))
    assert (subject, obj, moved) == (swap(users), swap(users), swap(graph))
    assert iris.is_aggregate_graph(str(iris.tenant(NEW)), str(moved))


# -- TC-09: policies that glue the id ---------------------------------------------------------


@pytest.mark.parametrize(
    ("templates", "expected"),
    [
        ({}, []),
        ({"tenant_template": "{base}t{tenant_id}"}, ["tenant_template"]),
        ({"aggregate_template": "{tenant}{id}"}, ["aggregate_template"]),
    ],
)
def test_glued_templates_names_the_templates_that_glue_the_tenant_id(
    templates: dict, expected: list[str]
):
    effective = iris_of(policy_settings(**templates)).effective_policy
    assert glued_templates(effective) == expected
