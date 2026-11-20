"""The toolkit's own migration chain: the versions it holds and what its 2 to 3 migration does (collection-has-part TC-1)."""

from rdf_persistence.iris.domain.layout import stamps_graph_iri
from rdf_persistence.migrations.services.migrations import (
    chain_of,
    load_migration,
    migration_request,
    versions,
)
from rdf_persistence.schema.services.vocabulary import TOOLKIT_MIGRATIONS, metamodel

SECOND_TO_THIRD = TOOLKIT_MIGRATIONS / "2__3.yaml"
STAMPS = stamps_graph_iri("https://example.org/")


def test_the_toolkits_chain_runs_from_version_one_to_three():
    _, chain = chain_of(metamodel(), TOOLKIT_MIGRATIONS)
    assert versions(chain) == ("1", "2", "3"), "version 3 follows version 2"


def test_the_migration_from_two_to_three_is_one_step_that_loads_and_makes_a_request():
    migration = load_migration(SECOND_TO_THIRD)  # refuses a prefixed name or a ?rp_ variable
    assert (migration.from_version, migration.to_version) == ("2", "3"), "it moves 2 to 3"
    assert migration.steps, "it has steps"
    assert len(migration.steps) == 1, "one step"
    assert migration_request(migration, STAMPS), "the step becomes a guarded update request"
