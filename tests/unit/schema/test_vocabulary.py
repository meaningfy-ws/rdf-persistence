"""The predicates the session writes are the ones the schema declares (PD-7, PD-8)."""

import shutil
from pathlib import Path

import pytest
import yaml
from rdflib import URIRef, plugin
from rdflib.parser import Parser

from rdf_persistence.access.domain.generated.rp_tenancy import TenantState
from rdf_persistence.core.domain.generated.rp_core import RegistryEntry, RegistryKind
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.schema.services import vocabulary
from rdf_persistence.schema.services.schema import API_ENTRYPOINTS_SCHEMA, load_schema
from rdf_persistence.schema.services.schema_structure import is_bookkeeping
from tests.schema_helpers import TENANT_STATE_IRIS

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
        ("started_at", vocabulary.STARTED_AT),
    ],
)
def test_each_constant_is_the_uri_of_its_slot(view, slot, predicate):
    assert slot_iri(view, slot) == predicate, f"{slot} differs from the schema"


def test_membership_is_dct_has_part_and_the_old_constant_is_gone(view):  # TC-8
    assert URIRef("http://purl.org/dc/terms/hasPart") == vocabulary.HAS_PART, "dcterms:hasPart"
    assert slot_iri(view, "has_part") == vocabulary.HAS_PART, "the constant comes from the slot"
    assert not hasattr(vocabulary, "HAD_MEMBER"), "removed, not aliased"


def test_the_reference_collection_mixin_is_a_dcmitype_collection(view):  # TC-8, DEC-4
    declared = URIRef(view.expand_curie(view.get_class("ReferenceCollection").class_uri))
    assert declared == URIRef("http://purl.org/dc/dcmitype/Collection"), "dcmitype:Collection"


def test_the_commit_marker_class_iri_is_the_class_uri_of_the_schema(view):
    declared = URIRef(view.expand_curie(view.get_class("CommitMarker").class_uri))
    assert declared == vocabulary.COMMIT_MARKER, "COMMIT_MARKER differs from the schema"


def test_a_commit_marker_is_an_id_and_the_time_the_transaction_started():
    from datetime import UTC, datetime

    from rdf_persistence.core.domain.generated.rp_core import CommitMarker

    started = datetime(2026, 11, 13, tzinfo=UTC)
    marker = CommitMarker(id="urn:uuid:00000000-0000-0000-0000-000000000001", started_at=started)
    assert marker.started_at == started, "the marker holds the start time"
    with pytest.raises(ValueError, match="started_at"):
        CommitMarker(id="urn:uuid:00000000-0000-0000-0000-000000000001")


def test_every_registry_slot_has_a_constant():
    registry_slots = set(RegistryEntry.model_fields)
    assert registry_slots == {"graph", "kind", "owned_by"}, (
        "a new RegistryEntry slot needs a constant"
    )


@pytest.mark.parametrize(
    ("enum", "mapping"),
    [(RegistryKind, vocabulary.REGISTRY_KIND_IRIS), (TenantState, TENANT_STATE_IRIS)],
)
def test_each_enum_member_maps_to_the_meaning_the_schema_declares(view, enum, mapping):
    values = view.get_enum(enum.__name__).permissible_values
    meanings = {m: URIRef(view.expand_curie(values[m.value].meaning)) for m in enum}
    assert dict(mapping) == meanings, f"{enum.__name__} members differ from the enum's meanings"
    assert set(mapping) == set(enum), "keyed by the generated enum, one entry per member"


def test_the_total_of_a_listing_is_the_predicate_of_the_page_slot_of_that_name():
    service = load_schema(API_ENTRYPOINTS_SCHEMA)
    assert URIRef(service.expand_curie(service.get_slot("total").slot_uri)) == vocabulary.TOTAL, (
        "the listing total is the predicate of the page slot"
    )


def test_each_serialisation_carries_the_media_type_the_schema_declares():  # TC-46
    assert dict(vocabulary.media_types(RdfFormat)) == {
        RdfFormat.TURTLE: "text/turtle",
        RdfFormat.RDFXML: "application/rdf+xml",
        RdfFormat.NTRIPLES: "application/n-triples",
        RdfFormat.JSONLD: "application/ld+json",
    }, "RdfFormat's media types differ from the schema's"


@pytest.mark.parametrize("fmt", list(RdfFormat), ids=lambda f: f.value)
def test_each_media_type_is_a_parser_rdflib_registers(fmt):  # TC-47
    media_type = vocabulary.media_types(RdfFormat)[fmt]
    assert plugin.get(media_type, Parser), f"rdflib registers no parser for {media_type}"


def test_a_serialisation_without_a_media_type_is_refused_by_name(tmp_path):  # TC-48
    folder = tmp_path / "model"
    shutil.copytree(METAMODEL.parent, folder, ignore=shutil.ignore_patterns("migrations"))
    path = folder / "rp_files.yaml"
    schema = yaml.safe_load(path.read_text())
    del schema["enums"]["RdfFormat"]["permissible_values"]["ntriples"]["annotations"]
    path.write_text(yaml.safe_dump(schema))
    with pytest.raises(ValueError, match="ntriples"):
        vocabulary.media_types(RdfFormat, view=load_schema(folder / "rp.yaml"))


@pytest.mark.parametrize(
    ("constant", "iri"),
    [
        ("PENDING_SINCE", "https://meaningfy.ws/ns/rdf-persistence#pendingSince"),
        ("RELAYED_AT", "https://meaningfy.ws/ns/rdf-persistence#relayedAt"),
        ("PUBLICATION_FAILED", "https://meaningfy.ws/ns/rdf-persistence#publicationFailed"),
        ("ABSENT_KEY_VALUE", "https://meaningfy.ws/ns/rdf-persistence#absentKeyValue"),
    ],
)
def test_a_plumbing_iri_is_its_literal_iri_in_the_metamodels_namespace(
    constant, iri
):  # PD-1, DEC-7
    value = getattr(vocabulary, constant)
    assert value == URIRef(iri), f"{constant} moved: {value}"
    assert value in vocabulary.RP, f"{constant} is outside the metamodel's default namespace"
