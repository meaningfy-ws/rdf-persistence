"""The names a consumer imports from the top-level package (DEC-6)."""

import importlib
import pkgutil

import pytest

import rdf_persistence
from rdf_persistence.domain import generated

INDEXED_NAMES = [
    "RpModel",
    "InvalidIri",
    "mint_aggregate_iri",
    "load_schema",
    "AccessRules",
    "Forbidden",
    "CallerAccess",
    "S3FileStore",
    "TokenVerifier",
    "JwksTokenVerifier",
    "Identity",
    "ZitadelIdentity",
    "zitadel_roles_claim",
    "IdentityUnavailable",
    "InvalidToken",
    "AccountSummary",
    "AggregateRoot",
    "StoredFile",
    "Principal",
    "TenantAccess",
    "Grant",
    "TenantState",
    "RegistryEntry",
    "Store",
    "FusekiStore",
    "DatabaseGone",
    "StoreUnavailable",
    "NotFound",
    "Conflict",
    "BadQuery",
    "open_session",
    "Tenancy",
    "GrantValidator",
    "RootValidator",
    "sweep",
    "FileStore",
    "TenantGone",
    "Session",
    "Mapper",
    "UnitOfWork",
    "new_part",
    "generated_models",
    "install_service",
    "ServiceKit",
    "Iris",
    "IriPolicy",
    "IdSource",
    "IdSpec",
    "IdKind",
    "DEFAULT_IRIS",
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


def declared_names() -> set[str]:
    """The classes and enums each generated module declares itself (the root module only re-exports)."""
    modules = [
        importlib.import_module(f"{generated.__name__}.{info.name}")
        for info in pkgutil.iter_modules(generated.__path__)
    ]
    return {
        name
        for module in modules
        for name, value in vars(module).items()
        if isinstance(value, type)
        and value.__module__ == module.__name__
        and name not in {"ConfiguredBaseModel", "LinkMLMeta"}
    }


def test_every_generated_public_class_and_enum_is_exported() -> None:
    generated_names = declared_names()
    assert "Principal" in generated_names, "the scan found no generated class"
    missing = generated_names - set(rdf_persistence.__all__)
    assert not missing, f"generated but not exported: {sorted(missing)}"
