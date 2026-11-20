"""The store name on the access record and the error for an unwired store (tenant-stores PD-1, PD-2, PD-10; TC-01, TC-02, TC-04).

TC-03 decodes through the mapper, a service: it is in ``tests/unit/tenancy/test_tenancy_stores.py``.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence import PersistenceError, StoreNotWired, TenantAccess
from tests.unit.builders import tenant_access

MIGRATIONS = Path(__file__).parents[3] / "rdf_persistence" / "model" / "migrations"


def with_store(name: str) -> TenantAccess:
    return TenantAccess(**{**tenant_access().model_dump(), "store_name": name})


@pytest.mark.parametrize("name", ["client-a", "a", "a" * 32])
def test_tc01_a_valid_store_name_is_accepted(name: str) -> None:
    assert with_store(name).store_name == name, "the name is kept as given"


@pytest.mark.parametrize("name", ["Client-A", "-a", "1a", "", "a" * 33])
def test_tc02_an_invalid_store_name_is_refused(name: str) -> None:
    with pytest.raises(ValidationError):
        with_store(name)


def test_tc04_the_lock_is_at_the_toolkits_version_3_and_its_chain_holds_both_migrations() -> None:
    lock = json.loads((MIGRATIONS / "schema.lock.json").read_text("utf-8"))
    assert str(lock["schema_version"]) == "3", "the lock is at version 3"
    assert sorted(p.name for p in MIGRATIONS.glob("*.yaml")) == ["1__2.yaml", "2__3.yaml"], (
        "the chain is 1 to 2 and 2 to 3"
    )


def test_store_not_wired_is_a_value_error_of_the_toolkit() -> None:
    assert issubclass(StoreNotWired, PersistenceError), "a toolkit error"
    assert issubclass(StoreNotWired, ValueError), "and a value error"
