"""The IRI and name rules of ``domain.iris`` are the schema's patterns (PD-6a); ``domain`` cannot read the schema, so this test pins them."""

import pytest

from rdf_persistence.domain import iris
from rdf_persistence.services.schema import PACKAGE_DIR, load_schema

VIEW = load_schema(PACKAGE_DIR / "model" / "service" / "rp_service.yaml")


def _unanchored(pattern: str) -> str:
    return pattern.removeprefix("^").removesuffix("$")


def test_the_prefix_rule_is_the_pattern_of_the_service_settings_prefix():
    declared = VIEW.induced_slot("prefix", "ServiceSettings").pattern
    assert iris._PREFIX.pattern == _unanchored(declared)


def test_the_segment_rule_is_the_pattern_of_url_segment():
    assert iris._SEGMENT.pattern == _unanchored(VIEW.get_slot("url_segment").pattern)


@pytest.mark.parametrize("prefix", ["li-b", "1lib", "Lib", "a" * 21])
def test_a_prefix_the_schema_refuses_is_refused(prefix):
    with pytest.raises(ValueError, match="prefix"):
        iris.system_database_name(prefix)


@pytest.mark.parametrize("segment", ["Books", "1books", "a.b", "a_b", "a~b"])
def test_a_segment_the_schema_refuses_is_refused(segment):
    with pytest.raises(ValueError, match="segment"):
        iris.mint_aggregate_iri("https://example.org/t", segment)
