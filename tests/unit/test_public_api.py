"""The names a consumer imports from the top-level package (DEC-6)."""

import importlib

import pytest

import rdf_persistence
from rdf_persistence.domain.generated import rp as generated

INDEXED_NAMES = [
    "RpModel",
    "AggregateRoot",
    "StoredFile",
    "Principal",
    "TenantAccess",
    "Grant",
    "TenantState",
    "RegistryEntry",
]


def test_all_lists_no_name_twice() -> None:
    names = rdf_persistence.__all__
    assert len(names) == len(set(names)), "__all__ lists a name twice"


@pytest.mark.parametrize("name", rdf_persistence.__all__)
def test_every_exported_name_imports_from_the_top_level(name: str) -> None:
    module = importlib.import_module("rdf_persistence")
    assert hasattr(module, name), f"{name} is in __all__ but not importable"


@pytest.mark.parametrize("name", INDEXED_NAMES)
def test_every_name_in_the_architecture_index_is_exported(name: str) -> None:
    assert name in rdf_persistence.__all__, f"{name} is listed in the architecture but not exported"


def test_every_generated_public_class_and_enum_is_exported() -> None:
    generated_names = {
        name
        for name, value in vars(generated).items()
        if isinstance(value, type)
        and value.__module__ == generated.__name__
        and name not in {"ConfiguredBaseModel", "LinkMLMeta"}
    }
    missing = generated_names - set(rdf_persistence.__all__)
    assert not missing, f"generated but not exported: {sorted(missing)}"
