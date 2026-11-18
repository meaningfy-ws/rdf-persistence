"""The IRI and name rules of ``domain.layout`` are the schema's patterns (PD-6a); ``domain`` cannot read the schema, so this test pins them."""

import pytest

from rdf_persistence.iris.domain import layout
from rdf_persistence.iris.services import iris
from rdf_persistence.schema.services.schema import IRIS_SCHEMA, PACKAGE_DIR, load_schema

VIEW = load_schema(IRIS_SCHEMA)
METAMODEL = load_schema(PACKAGE_DIR / "model" / "rp_core.yaml")


def _unanchored(pattern: str) -> str:
    return pattern.removeprefix("^").removesuffix("$")


def test_the_prefix_rule_is_the_pattern_of_the_service_settings_prefix():
    declared = VIEW.induced_slot("prefix", "ServiceSettings").pattern
    assert layout._PREFIX.pattern == _unanchored(declared), (
        "the prefix rule is the pattern the schema declares"
    )


def test_the_segment_rule_is_the_pattern_of_url_segment():
    assert layout._SEGMENT.pattern == _unanchored(METAMODEL.get_slot("url_segment").pattern), (
        "the segment rule is the pattern the schema declares"
    )


def test_the_tenant_segment_of_the_settings_repeats_the_pattern_of_url_segment():
    """The iris schema does not import the metamodel, so it states the pattern again (see its slot)."""
    declared = VIEW.induced_slot("tenant_segment", "ServiceSettings").pattern
    assert declared == METAMODEL.get_slot("url_segment").pattern, (
        "the settings' tenant segment and the metamodel's url_segment follow one pattern"
    )


@pytest.mark.parametrize("prefix", ["li-b", "1lib", "Lib", "a" * 21])
def test_a_prefix_the_schema_refuses_is_refused(prefix):
    with pytest.raises(ValueError, match="prefix"):
        layout.system_database_name(prefix)


@pytest.mark.parametrize("segment", ["Books", "1books", "a.b", "a_b", "a~b"])
def test_a_segment_the_schema_refuses_is_refused(segment):
    with pytest.raises(ValueError, match="segment"):
        iris.DEFAULT_IRIS.mint_aggregate("https://example.org/t", cls_type="", rp_path=segment)
