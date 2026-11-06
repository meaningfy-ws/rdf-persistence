"""The predicates the session writes are the ones the schema declares (PD-7, PD-8)."""

from pathlib import Path

import pytest
from rdflib import URIRef

from rdf_persistence.domain.generated.rp_core import RegistryEntry, RegistryKind
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.services import vocabulary
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import is_bookkeeping

METAMODEL = Path(__file__).parents[3] / "rdf_persistence" / "model" / "rp.yaml"


@pytest.fixture(scope="module")
def view():
    return load_schema(METAMODEL)


def slot_iri(view, name: str) -> URIRef:
    return URIRef(view.expand_curie(view.get_slot(name).slot_uri))


def test_the_bookkeeping_predicates_are_exactly_the_bookkeeping_slots_of_the_schema(view):
    declared = {slot_iri(view, s.name) for s in view.all_slots().values() if is_bookkeeping(s)}
    assert declared == set(vocabulary.BOOKKEEPING_PREDICATES), (
        "a bookkeeping slot without a constant, or a constant without a slot"
    )


@pytest.mark.parametrize(
    ("slot", "predicate"),
    [
        ("version", vocabulary.VERSION),
        ("created", vocabulary.CREATED),
        ("modified", vocabulary.MODIFIED),
        ("creator", vocabulary.CREATOR),
        ("contributor", vocabulary.CONTRIBUTOR),
        ("graph", vocabulary.REGISTRY_GRAPH),
        ("kind", vocabulary.REGISTRY_KIND),
        ("owned_by", vocabulary.REGISTRY_OWNED_BY),
        ("state", vocabulary.STATE),
    ],
)
def test_each_constant_is_the_uri_of_its_slot(view, slot, predicate):
    assert slot_iri(view, slot) == predicate, f"{slot} differs from the schema"


def test_every_registry_slot_has_a_constant():
    registry_slots = set(RegistryEntry.model_fields)
    assert registry_slots == {"graph", "kind", "owned_by"}, (
        "a new RegistryEntry slot needs a constant"
    )


@pytest.mark.parametrize(
    ("enum", "mapping"),
    [(RegistryKind, vocabulary.REGISTRY_KIND_IRIS), (TenantState, vocabulary.TENANT_STATE_IRIS)],
)
def test_each_enum_member_maps_to_the_meaning_the_schema_declares(view, enum, mapping):
    values = view.get_enum(enum.__name__).permissible_values
    meanings = {m: URIRef(view.expand_curie(values[m.value].meaning)) for m in enum}
    assert dict(mapping) == meanings, f"{enum.__name__} members differ from the enum's meanings"
    assert set(mapping) == set(enum), "keyed by the generated enum, one entry per member"


def test_the_total_of_a_listing_is_the_predicate_of_the_page_slot_of_that_name():
    service = load_schema(vocabulary.SERVICE_MODEL)
    assert URIRef(service.expand_curie(service.get_slot("total").slot_uri)) == vocabulary.TOTAL
