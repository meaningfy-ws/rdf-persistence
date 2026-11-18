"""The chain of a schema view and a folder, and the helpers that read a chain (schema-migrations PD-24.2, PD-24.3)."""

import copy

import pytest

from rdf_persistence.core.domain.exceptions import InvalidMigration
from rdf_persistence.migrations.services.migrations import (
    chain_of,
    current_version,
    first_version,
    versions,
)
from rdf_persistence.schema.services.schema import load_schema
from tests.toy import TOY_SCHEMA


def test_the_chain_of_a_view_ends_at_the_schemas_version_and_names_its_id(tmp_path):
    view = load_schema(TOY_SCHEMA)
    schema_id, chain = chain_of(view, tmp_path)
    assert schema_id == str(view.schema.id), "the schema id is the view's"
    assert versions(chain) == (str(view.schema.version),), (
        "with no file, the chain is the current version"
    )


def test_the_helpers_read_the_ends_of_a_chain(tmp_path):
    _, chain = chain_of(load_schema(TOY_SCHEMA), tmp_path)
    assert first_version(chain) == current_version(chain), (
        "a chain of one version starts and ends at it"
    )


@pytest.mark.parametrize("missing", [None, ""], ids=["no version", "an empty version"])
def test_a_schema_with_no_version_is_refused_naming_it_and_the_key_to_add(tmp_path, missing):
    view = copy.deepcopy(load_schema(TOY_SCHEMA))
    view.schema.version = missing
    with pytest.raises(InvalidMigration) as refused:
        chain_of(view, tmp_path)
    assert str(view.schema.id) in str(refused.value), "the schema id is named"
    assert "add version:" in str(refused.value), "and the fix is said"
