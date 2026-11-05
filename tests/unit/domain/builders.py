"""Small builders for metamodel objects, so each test states only what it varies."""

from typing import Any

from rdf_persistence import Grant, TenantAccess

TENANT = "https://example.org/tenant/acme"
ALICE = "https://example.org/user/alice"


def grant(**overrides: Any) -> Grant:
    """A role grant for Alice on the tenant; override or add any field."""
    fields: dict[str, Any] = {"assignee": ALICE, "target": TENANT, "role": "editor"}
    fields.update(overrides)
    return Grant(**fields)


def tenant_access(**overrides: Any) -> TenantAccess:
    """An active tenant access record; override or add any field."""
    fields: dict[str, Any] = {
        "id": TENANT,
        "label": "Acme",
        "state": "active",
        "database_name": "acme",
    }
    fields.update(overrides)
    return TenantAccess(**fields)
