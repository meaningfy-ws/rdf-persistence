"""Schema-level facts of the metamodel that the generated classes cannot show."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from rdflib import URIRef

from rdf_persistence.domain.generated.rp_provenance import Generation, Invalidation, Replace
from rdf_persistence.domain.generated.rp_workflow import Transition
from rdf_persistence.services import vocabulary
from rdf_persistence.services.schema import SERVICE_SCHEMA, load_schema
from rdf_persistence.services.schema_structure import is_internal, is_owned
from tests.toy import ADA, book_iri, toy_mapper

MODEL = Path(__file__).parents[3] / "rdf_persistence" / "model"
LIBRARY = Path(__file__).parents[2] / "fixtures" / "library"
AT = datetime(2026, 11, 14, tzinfo=UTC)
PROV_ASSOCIATED = URIRef("http://www.w3.org/ns/prov#wasAssociatedWith")
# The fields of Transition (message-bus PD-11), and whether each is required: the three the toolkit
# computes and the payload slots are optional, so that a command can be built without them.
TRANSITION_FIELDS = {
    "used_resource": True,
    "from_state_iri": False,
    "to_state_iri": False,
    "started_at_time": False,
    "transition_comment": False,
    "to_state": False,
    "expected_version": False,
    "body_value": False,
    "id": True,
    "was_associated_with": False,
}


@pytest.mark.parametrize(
    ("schema", "name", "class_uri"),
    [
        (MODEL / "rp.yaml", "Grant", "ODRL:Permission"),
        (MODEL / "rp.yaml", "Prohibition", "ODRL:Prohibition"),
    ],
)
def test_stored_rule_is_typed_as_its_odrl_class(schema: Path, name: str, class_uri: str) -> None:
    view = load_schema(schema)
    assert view.get_class(name).class_uri == class_uri, f"{name} is not typed {class_uri}"


@pytest.mark.parametrize("name", ["Grant", "Prohibition"])
def test_rules_share_one_abstract_rule_class(name: str) -> None:
    view = load_schema(MODEL / "rp.yaml")
    assert view.get_class(name).is_a == "Rule", f"{name} does not extend Rule"
    assert view.get_class("Rule").abstract, "Rule must be abstract"


def test_database_name_is_internal() -> None:
    slot = load_schema(MODEL / "rp.yaml").get_slot("database_name")
    assert is_internal(slot), "database_name must be marked internal"


@pytest.mark.parametrize(
    ("schema", "class_name", "slot", "slot_uri"),
    [
        (MODEL / "rp.yaml", "Grant", "target", "ODRL:target"),
        (SERVICE_SCHEMA, "Page", "items", "rp:items"),
        (LIBRARY / "library.yaml", "Grant", "target", "ODRL:target"),
        (MODEL / "rp.yaml", "Comment", "has_target", "oa:hasTarget"),
        (MODEL / "rp.yaml", "Comment", "body_value", "oa:bodyValue"),
        (MODEL / "rp.yaml", "Comment", "motivated_by", "oa:motivatedBy"),
        (MODEL / "rp.yaml", "Comment", "comment_audience", "rp:audience"),
        (MODEL / "rp.yaml", "Comment", "comment_references", "dcterms:references"),
        (MODEL / "rp.yaml", "Comment", "replies_to", "rp:repliesTo"),
        (MODEL / "rp.yaml", "Comment", "from_state_iri", "rp:fromState"),
        (MODEL / "rp.yaml", "Comment", "to_state_iri", "rp:toState"),
        (MODEL / "rp.yaml", "Transition", "from_state_iri", "rp:fromState"),
        (MODEL / "rp.yaml", "Transition", "to_state_iri", "rp:toState"),
        (MODEL / "rp.yaml", "Transition", "used_resource", "prov:used"),
        (MODEL / "rp.yaml", "Transition", "started_at_time", "prov:startedAtTime"),
        (MODEL / "rp.yaml", "Transition", "transition_comment", "rp:transitionComment"),
        (MODEL / "rp.yaml", "Transition", "was_associated_with", "prov:wasAssociatedWith"),
        (MODEL / "rp.yaml", "UnderWorkflow", "workflow_status", "ADMS:status"),
        (LIBRARY / "library.yaml", "Book", "workflow_status", "ADMS:status"),
    ],
)
def test_a_slot_name_shared_across_the_imports_keeps_its_own_predicate(
    schema: Path, class_name: str, slot: str, slot_uri: str
) -> None:
    """A new module's slot must not take the name of another's (one slot namespace per closure)."""
    induced = load_schema(schema).induced_slot(slot, class_name)
    assert induced.slot_uri == slot_uri, (
        f"{class_name}.{slot} is {induced.slot_uri}, not {slot_uri}"
    )


def test_an_activity_has_the_four_optional_slots_and_owns_its_parts() -> None:
    view = load_schema(MODEL / "rp.yaml")
    for name in ("started_at_time", "ended_at_time", "generations", "invalidations"):
        assert not view.induced_slot(name, "Activity").required, f"Activity.{name} is optional"
    for name in ("generations", "invalidations"):
        slot = view.induced_slot(name, "Activity")
        assert slot.multivalued and is_owned(slot), f"Activity.{name} is an owned list"


def test_the_session_writes_five_of_the_eight_toolkit_filled_slots() -> None:
    five = {
        "started_at_time",
        "ended_at_time",
        "was_associated_with",
        "generations",
        "invalidations",
    }
    computed = {"from_state_iri", "to_state_iri", "transition_comment"}  # a transition's (PD-11)
    assert set(vocabulary.TOOLKIT_FILLED) == five | computed, "annotated toolkit_filled"
    assert set(vocabulary.SESSION_FILLED) == five, "the literal tuple, a subset of those"


def test_a_replace_with_an_agent_round_trips_with_one_associated_principal() -> None:
    iri = "urn:uuid:00000000-0000-0000-0000-000000000001"
    replace = Replace(id=iri, was_associated_with=[ADA])
    mapper = toy_mapper()
    graph = mapper.to_graph(replace)
    agents = list(graph.objects(URIRef(iri), PROV_ASSOCIATED))
    assert agents == [URIRef(ADA)], "one prov:wasAssociatedWith IRI"
    assert mapper.from_graph(Replace, iri, graph, None) == replace, "the same model"


@pytest.mark.parametrize("cls", [Generation, Invalidation])
def test_a_part_needs_a_version_and_not_a_class(cls: type[Generation | Invalidation]) -> None:
    part = {"activity": "urn:uuid:1", "at_time": AT, "entity": book_iri(1)}
    with pytest.raises(ValidationError):
        cls(**part)
    assert cls(**part, entity_version="v1").entity_class is None, "valid without a class"


def test_a_replace_with_one_generation_round_trips_through_the_mapper() -> None:
    iri = "urn:uuid:00000000-0000-0000-0000-000000000001"
    part = Generation(activity=iri, at_time=AT, entity=book_iri(1), entity_version="v2")
    replace = Replace(id=iri, generations=[part])
    mapper = toy_mapper()
    assert mapper.from_graph(Replace, iri, mapper.to_graph(replace), None) == replace, (
        "the same model"
    )


def test_a_transition_has_its_fields_and_requires_only_the_aggregate_it_used() -> None:
    required = {
        name: field.is_required()
        for name, field in Transition.model_fields.items()
        if name in TRANSITION_FIELDS
    }
    assert required == TRANSITION_FIELDS, "these fields, so required"
