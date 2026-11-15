"""The store name on the access record and the error for an unwired store (tenant-stores PD-1, PD-2, PD-10; TC-01 to TC-04)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence import PersistenceError, StoreNotWired, TenantAccess
from rdf_persistence.domain.generated import rp_core, rp_tenancy
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.mapper import Mapper, generated_models
from tests.unit.domain.builders import TENANT, tenant_access

MIGRATIONS = Path(__file__).parents[3] / "rdf_persistence" / "model" / "migrations"


def with_store(name: str) -> TenantAccess:
    return TenantAccess(**{**tenant_access().model_dump(), "store_name": name})


@pytest.mark.parametrize("name", ["client-a", "a", "a" * 32])
def test_tc01_a_valid_store_name_is_accepted(name: str) -> None:
    assert with_store(name).store_name == name


@pytest.mark.parametrize("name", ["Client-A", "-a", "1a", "", "a" * 33])
def test_tc02_an_invalid_store_name_is_refused(name: str) -> None:
    with pytest.raises(ValidationError):
        with_store(name)


def test_tc03_a_record_written_without_a_store_name_decodes_with_none() -> None:
    mapper = Mapper(v.metamodel(), generated_models(rp_tenancy, rp_core))
    graph = mapper.to_graph(tenant_access())
    decoded = mapper.from_graph(TenantAccess, TENANT, graph, graph_iri(TENANT))
    assert decoded.store_name is None


def test_tc04_the_lock_stays_at_version_2_and_no_migration_is_added() -> None:
    lock = json.loads((MIGRATIONS / "schema.lock.json").read_text("utf-8"))
    assert str(lock["schema_version"]) == "2"
    assert sorted(p.name for p in MIGRATIONS.glob("*.yaml")) == ["1__2.yaml"]


def test_store_not_wired_is_a_value_error_of_the_toolkit() -> None:
    assert issubclass(StoreNotWired, PersistenceError)
    assert issubclass(StoreNotWired, ValueError)
