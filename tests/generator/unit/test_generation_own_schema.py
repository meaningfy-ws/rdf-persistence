"""The generator's own schema is not checked with the consumers' class-level rules (PD-5, error matrix)."""

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation.checks.boundary import boundary_problems
from rdf_persistence_generation.checks.hard import hard_problems
from rdf_persistence_generation.config import GENERATION_MODEL


def test_the_generators_own_schema_gets_the_toolkit_rules_not_the_consumers() -> None:
    """Error matrix: after the move the generator's schema still passes as a toolkit schema."""
    folder = GENERATION_MODEL.parent
    view = load_schema(GENERATION_MODEL)

    assert boundary_problems(view, folder) == [], (
        "the consumer boundary rules fired on the generator's schema"
    )
    assert hard_problems(view, folder) == [], (
        "the consumer hard rules fired on the generator's schema"
    )
