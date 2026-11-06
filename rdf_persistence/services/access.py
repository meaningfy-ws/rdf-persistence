"""Access control (PD-9, PD-10): role definitions, grant sets, one caller's access, and the check.

The check answers in the order of the design's worked example: a tenant that is not active is 404; a
matching Prohibition is 403; a caller who can see nothing of the tenant or the aggregate is 404; a
tenant role, a direct permission or a global role that permits the action allows it; anything else
is 403.

A Prohibition of ``read`` forbids every action, since each of them implies ``read``; a Prohibition
of any other action forbids that action only.
"""

from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import ValidationError
from rdflib import URIRef
from rdflib.query import ResultRow

from rdf_persistence.domain.exceptions import (
    Forbidden,
    InvalidRoleDefinition,
    NotFound,
    UnknownRole,
)
from rdf_persistence.domain.generated.rp_access import (
    Action,
    Grant,
    Prohibition,
    RoleDefinition,
    RoleLevel,
)
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    CallerAccess,
    GrantSet,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import access_iri, graph_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.store import Store

# The access record's state, and the rules that name one principal: one row per rule.
SELECT_CALLER_ACCESS = """
SELECT ?state ?link ?target ?role ?action WHERE {
  GRAPH $graph {
    $record $p_state ?state .
    OPTIONAL {
      VALUES ?link { $p_grant $p_prohibition }
      $record ?link ?rule .
      ?rule $p_assignee $principal ; $p_target ?target .
      OPTIONAL { ?rule $p_role ?role }
      OPTIONAL { ?rule $p_action ?action }
    }
  }
}
"""
_IMPLY_READ = frozenset({Action.MODIFY, Action.DELETE, Action.ADMINISTER})
_STATES = {iri: state for state, iri in v.TENANT_STATE_IRIS.items()}
_ACTIONS = {iri: action for action, iri in v.ACTION_IRIS.items()}


def load_role_definitions(path: Path) -> list[RoleDefinition]:
    """The role definitions in the YAML file ``path``, validated against ``rp_access``.

    Raises:
        InvalidRoleDefinition: The file cannot be read, is not a YAML list, or an entry is invalid;
            the message names the entry.
    """
    try:
        data = yaml.safe_load(path.read_text())
    except OSError as error:
        raise InvalidRoleDefinition(f"cannot read the role definitions {path}: {error}") from error
    except yaml.YAMLError as error:
        raise InvalidRoleDefinition(f"{path} is not valid YAML: {error}") from error
    if not isinstance(data, list):
        raise InvalidRoleDefinition(f"{path} must hold a list of role definitions")
    return [_definition(path, number, entry) for number, entry in enumerate(data, start=1)]


def _definition(path: Path, number: int, entry: object) -> RoleDefinition:
    if not isinstance(entry, dict):
        raise InvalidRoleDefinition(f"{path}: entry {number} is not a mapping: {entry!r}")
    named = f" (role {entry['role']!r})" if "role" in entry else ""
    try:
        return RoleDefinition.model_validate(entry)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']} (got {e['input']!r})"
            for e in error.errors()
        )
        raise InvalidRoleDefinition(f"{path}: entry {number}{named}: {problems}") from error


def validate_grants(grants: GrantSet, definitions: Iterable[RoleDefinition]) -> None:
    """Check that every role a grant names is defined for a tenant or an aggregate.

    Duplicate keys are refused when the ``GrantSet`` is built (its ``grant_key`` validator). A role
    that is defined only at system level comes from the token, so it cannot be granted.

    Raises:
        UnknownRole: A grant names a role no definition of level tenant or aggregate defines.
    """
    grantable = {d.role for d in definitions if d.level != RoleLevel.SYSTEM}
    for grant in grants.grants or []:
        if grant.role is not None and grant.role not in grantable:
            raise UnknownRole(f"grant of unknown role {grant.role!r}")


def _caller_query(tenant: str, principal: str) -> str:
    record = access_iri(tenant)
    return fill(
        SELECT_CALLER_ACCESS,
        graph=term(graph_iri(str(record))),
        record=term(record),
        principal=term(URIRef(principal)),
        p_state=term(v.STATE),
        p_grant=term(v.GRANT),
        p_prohibition=term(v.PROHIBITION),
        p_assignee=term(v.ASSIGNEE),
        p_target=term(v.TARGET),
        p_role=term(v.ROLE),
        p_action=term(v.ACTION),
    )


async def load_caller_access(
    store: Store, system_database: str, tenant: str, principal: str
) -> CallerAccess:
    """The tenant's state and the grants and prohibitions that name ``principal``, in one query.

    Raises:
        NotFound: The tenant has no access record.
        ValueError: ``tenant`` or ``principal`` is not usable in a query (``SparqlError``).
    """
    result = await store.query(system_database, _caller_query(tenant, principal))
    rows = [row for row in result if isinstance(row, ResultRow)]
    if not rows:
        raise NotFound(f"no access record for {tenant}")
    return _caller_access(tenant, principal, rows)


def _caller_access(tenant: str, principal: str, rows: list[ResultRow]) -> CallerAccess:
    rules = [_rule(principal, row) for row in rows if row.link is not None]
    return CallerAccess(
        tenant=tenant,
        state=_STATES[URIRef(rows[0].state)],
        grants=[r for r in rules if isinstance(r, Grant)] or None,
        prohibitions=[r for r in rules if isinstance(r, Prohibition)] or None,
    )


def _rule(principal: str, row: ResultRow) -> Grant | Prohibition:
    """The grant or prohibition one row of ``SELECT_CALLER_ACCESS`` holds."""
    action = _ACTIONS[URIRef(row.action)] if row.action is not None else None
    if row.link == v.GRANT:
        role = str(row.role) if row.role is not None else None
        return Grant(assignee=principal, target=str(row.target), role=role, action=action)
    return Prohibition(assignee=principal, target=str(row.target), action=action)


class AccessRules:
    """Decides whether a caller may take an action on the tenant or on one of its aggregates."""

    def __init__(self, role_definitions: Iterable[RoleDefinition]) -> None:
        self._permits: dict[tuple[RoleLevel, str], set[Action]] = {}
        for definition in role_definitions:
            key = (RoleLevel(definition.level), definition.role)
            self._permits.setdefault(key, set()).update(definition.actions)

    def allowed(
        self, caller: VerifiedCaller, access: CallerAccess, target_iri: str, action: Action
    ) -> None:
        """Return if ``caller`` may take ``action`` on ``target_iri``.

        ``target_iri`` is the tenant IRI for a tenant-scope action (listing, creating, administering,
        deleting the tenant), or an aggregate's root IRI.

        Raises:
            NotFound: The tenant is not active, or the caller can see nothing of it or of the aggregate.
            Forbidden: A Prohibition forbids the action, or the caller may see but not take it.
        """
        if access.state != TenantState.ACTIVE:
            raise NotFound(f"no tenant {access.tenant}")
        scope = (
            {access.tenant, str(graph_iri(target_iri))}
            if target_iri != access.tenant
            else {access.tenant}
        )
        if self._prohibited(caller, access, scope, action):
            raise Forbidden(f"{action.value} is prohibited")
        granted = self._granted_actions(caller, access, scope)
        if granted is None:
            raise NotFound(f"nothing of {target_iri} is visible to the caller")
        if action not in granted and not (action == Action.READ and granted & _IMPLY_READ):
            raise Forbidden(f"{action.value} is not permitted")

    def _granted_actions(
        self, caller: VerifiedCaller, access: CallerAccess, scope: set[str]
    ) -> set[Action] | None:
        """What the caller's grants in ``scope`` and global roles permit; None if they show nothing."""
        sets = [*self._grant_sets(caller, access, scope), *self._system_sets(caller)]
        return set().union(*sets) if sets else None

    def _grant_sets(
        self, caller: VerifiedCaller, access: CallerAccess, scope: set[str]
    ) -> list[set[Action]]:
        return [
            self._granted(g, access.tenant)
            for g in access.grants or []
            if g.assignee == caller.principal and g.target in scope
        ]

    def _system_sets(self, caller: VerifiedCaller) -> list[set[Action]]:
        keys = [(RoleLevel.SYSTEM, role) for role in caller.global_roles or []]
        return [self._permits[key] for key in keys if key in self._permits]

    @staticmethod
    def _prohibited(
        caller: VerifiedCaller, access: CallerAccess, scope: set[str], action: Action
    ) -> bool:
        return any(
            p.assignee == caller.principal
            and p.target in scope
            and p.action in (action, Action.READ)
            for p in access.prohibitions or []
        )

    def _granted(self, grant: Grant, tenant: str) -> set[Action]:
        if grant.action is not None:
            return {grant.action}
        level = RoleLevel.TENANT if grant.target == tenant else RoleLevel.AGGREGATE
        return self._permits.get((level, grant.role or ""), set())
