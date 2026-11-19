"""Small builders for metamodel objects, so each test states only what it varies."""

from rdf_persistence import Action, Grant, Prohibition, TenantAccess, TenantState

TENANT = "https://example.org/tenant/acme"
ALICE = "https://example.org/user/alice"
DATABASE = "acme-t-" + "0" * 32
ACTIVE = TenantState("active")


def grant(
    *,
    assignee: str = ALICE,
    target: str = TENANT,
    role: str | None = "editor",
    action: Action | None = None,
) -> Grant:
    """A role grant for Alice on the tenant; pass ``role=None, action=...`` for a direct grant."""
    return Grant(assignee=assignee, target=target, role=role, action=action)


def tenant_access(
    *,
    label: str = "Acme",
    state: TenantState = ACTIVE,
    database_name: str = DATABASE,
    grants: list[Grant] | None = None,
    prohibitions: list[Prohibition] | None = None,
) -> TenantAccess:
    """An active tenant access record."""
    return TenantAccess(
        id=TENANT,
        label=label,
        state=state,
        database_name=database_name,
        grants=grants,
        prohibitions=prohibitions,
    )
