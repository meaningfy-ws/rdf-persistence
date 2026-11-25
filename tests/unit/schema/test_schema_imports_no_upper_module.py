"""The ``schema`` package reads the stored-file class and the tenant states from the schema, never from a theme module (PD-8, DEC-6)."""

from rdf_persistence.schema.services import schema_structure
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.vocabulary import METAMODEL, TENANT_STATE_IRIS


def test_the_stored_file_class_is_the_class_whose_class_uri_is_rp_stored_file() -> None:
    view = load_schema(METAMODEL)
    named = schema_structure.stored_file_class(view)
    assert named == "StoredFile", "the class named is the one with class_uri rp:StoredFile"
    assert view.get_class(named).class_uri == "rp:StoredFile"


def test_the_tenant_state_iris_are_the_meanings_of_the_tenancy_enum() -> None:
    view = load_schema(METAMODEL)
    values = view.get_enum("TenantState").permissible_values
    expected = {text: view.expand_curie(str(pv.meaning)) for text, pv in values.items()}
    assert {text: str(iri) for text, iri in TENANT_STATE_IRIS.items()} == expected
    assert set(expected) == {"active", "deleting"}, "the states of a tenant"
