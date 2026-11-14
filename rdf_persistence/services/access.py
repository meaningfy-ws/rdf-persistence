"""Access control (PD-9, PD-10): role definitions, grant sets, one caller's access, and the check.

The check answers in the order of the design's worked example: a tenant that is not active is 404; a
matching Prohibition is 403; a caller who can see nothing of the tenant or the aggregate is 404; a
tenant role, a direct permission or a global role that permits the action allows it; anything else
is 403.

A Prohibition of ``read`` forbids every action, since each of them implies ``read``; a Prohibition
of any other action forbids that action only.
"""

import copy
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import yaml
from pydantic import ValidationError
from rdflib import Graph, URIRef

from rdf_persistence.domain.exceptions import (
    Forbidden,
    InvalidGrant,
    InvalidRoleDefinition,
    NotFound,
    SparqlError,
    UnknownRole,
)
from rdf_persistence.domain.generated import rp_access, rp_core, rp_tenancy
from rdf_persistence.domain.generated.rp_access import (
    Action,
    Grant,
    Prohibition,
    RoleDefinition,
    RoleLevel,
)
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    CallerAccess,
    GrantSet,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris, graph_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.mapper import Mapper, generated_models
from rdf_persistence.services.store import Store

# The access record's own statements, and the rules that name one principal with their parts.
CONSTRUCT_CALLER_ACCESS = """
CONSTRUCT { $record ?p ?o . ?rule ?rule_p ?rule_o } WHERE {
  GRAPH $graph {
    {
      $record ?p ?o .
      FILTER (?p NOT IN ($p_grants, $p_prohibitions))
    } UNION {
      VALUES ?p { $p_grants $p_prohibitions }
      $record ?p ?rule .
      ?rule $p_assignee $principal ; ?rule_p ?rule_o .
      BIND (?rule AS ?o)
    }
  }
}
"""
# Every action other than read implies read at the same scope (PD-9).
_IMPLY_READ = frozenset(Action) - {Action.READ}
ACTIONS = tuple(Action)  # the schema's order, which is the order a read lists them in


def load_role_definitions(path: Path) -> list[RoleDefinition]:
    """The role definitions in the YAML file ``path``, validated against ``rp_access``.

    Raises:
        InvalidRoleDefinition: The file cannot be read, is not a YAML list, an entry is invalid
            (no actions included), or a role is defined twice at one level; the message names the entry.
    """
    try:
        data = yaml.safe_load(path.read_text())
    except OSError as error:
        raise InvalidRoleDefinition(f"cannot read the role definitions {path}: {error}") from error
    except yaml.YAMLError as error:
        raise InvalidRoleDefinition(f"{path} is not valid YAML: {error}") from error
    if not isinstance(data, list):
        raise InvalidRoleDefinition(f"{path} must hold a list of role definitions")
    definitions: dict[tuple[RoleLevel, str], RoleDefinition] = {}
    for number, entry in enumerate(data, start=1):
        definition = _definition(path, number, entry)
        key = (RoleLevel(definition.level), definition.role)
        if key in definitions:
            raise InvalidRoleDefinition(
                f"{path}: entry {number} (role {definition.role!r}) is defined twice at level "
                f"{key[0].value}"
            )
        definitions[key] = definition
    return list(definitions.values())


def _definition(path: Path, number: int, entry: object) -> RoleDefinition:
    if not isinstance(entry, dict):
        raise InvalidRoleDefinition(f"{path}: entry {number} is not a mapping: {entry!r}")
    named = f" (role {entry['role']!r})" if "role" in entry else ""
    try:
        definition = RoleDefinition.model_validate(entry)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']} (got {e['input']!r})"
            for e in error.errors()
        )
        raise InvalidRoleDefinition(f"{path}: entry {number}{named}: {problems}") from error
    if not definition.actions:
        raise InvalidRoleDefinition(f"{path}: entry {number}{named}: actions must not be empty")
    return definition


def _level(target: str, tenant: str) -> RoleLevel:
    """The level a grant on ``target`` applies at: the tenant's, or one aggregate's."""
    return RoleLevel.TENANT if target == tenant else RoleLevel.AGGREGATE


def _gate(action: Action, is_tenant: bool) -> Action:
    """The action a route needs to do ``action`` to the tenant (``administer`` for delete) or to an aggregate."""
    return Action.ADMINISTER if is_tenant and action == Action.DELETE else action


@cache
def _access_mapper() -> Mapper:
    return Mapper(v.metamodel(), generated_models(rp_access, rp_core, rp_tenancy))


async def load_caller_access(
    store: Store, system_database: str, tenant: str, principal: str, *, iris: Iris = DEFAULT_IRIS
) -> CallerAccess:
    """The tenant's state and the grants and prohibitions that name ``principal``, in one query.

    The access record is read with one ``CONSTRUCT`` that keeps its own statements and only the
    rules of ``principal``, and decoded by the mapper. ``iris`` is the IRI policy that says where the
    record is (default: the default policy).

    Raises:
        NotFound: The tenant has no access record, or the record cannot be decoded (no state or
            two, an unknown state or action).
        SparqlError: ``tenant`` or ``principal`` is not usable in a query (a ``ValueError``).
    """
    record = iris.access(tenant)
    text = fill(
        CONSTRUCT_CALLER_ACCESS,
        graph=term(graph_iri(str(record))),
        record=term(record),
        principal=term(URIRef(principal)),
        p_grants=term(v.GRANTS),
        p_prohibitions=term(v.PROHIBITIONS),
        p_assignee=term(v.ASSIGNEE),
    )
    stored = (await store.query(system_database, text)).graph
    if stored is None or (record, None, None) not in stored:
        raise NotFound(f"no access record for {tenant}")
    return _caller_access(tenant, record, stored)


def _caller_access(tenant: str, record: URIRef, stored: Graph) -> CallerAccess:
    if len(set(stored.objects(record, v.STATE))) != 1:
        raise NotFound(f"the access record of {tenant} must have exactly one state")
    try:
        decoded = _access_mapper().from_graph(
            TenantAccess, str(record), stored, graph_iri(str(record))
        )
    except (ValidationError, ValueError) as error:
        raise NotFound(f"the access record of {tenant} cannot be read: {error}") from error
    return CallerAccess(
        tenant=tenant,
        state=decoded.state,
        grants=decoded.grants,
        prohibitions=decoded.prohibitions,
    )


class AccessRules:
    """Decides whether a caller may take an action on the tenant or on one of its aggregates."""

    def __init__(
        self, role_definitions: Iterable[RoleDefinition], iris: Iris = DEFAULT_IRIS
    ) -> None:
        """``iris`` is the IRI policy that says what an aggregate and its graph are (default: the default policy)."""
        self._iris = iris
        self._permits: dict[tuple[RoleLevel, str], set[Action]] = {}
        for definition in role_definitions:
            key = (RoleLevel(definition.level), definition.role)
            self._permits.setdefault(key, set()).update(definition.actions)

    def with_iris(self, iris: Iris) -> "AccessRules":
        """The same role permits under the IRI policy ``iris``; this object is unchanged."""
        rebound = copy.copy(self)
        rebound._iris = iris
        return rebound

    def validate_grants(self, grants: GrantSet, tenant: str) -> None:
        """Check that ``check`` could honour every grant and prohibition of ``grants`` in ``tenant``.

        A target is the tenant IRI or the graph IRI of one of its aggregates; an assignee is an IRI.
        A role grant names a role defined at the target's level (a tenant role on the tenant, an
        aggregate role on an aggregate graph); a role defined only at system level comes from the
        token and cannot be granted. Duplicate keys are refused when the ``GrantSet`` is built.

        Raises:
            InvalidGrant: A target is foreign to the tenant, or an assignee is not an IRI.
            UnknownRole: A grant names a role not defined at its target's level.
        """
        rules: list[Grant | Prohibition] = [*(grants.grants or []), *(grants.prohibitions or [])]
        for rule in rules:
            self._validate_ends(rule, tenant)
        for grant in grants.grants or []:
            level = _level(grant.target, tenant)
            if grant.role is not None and (level, grant.role) not in self._permits:
                raise UnknownRole(f"no {level.value}-level role {grant.role!r} to grant")

    def _validate_ends(self, rule: Grant | Prohibition, tenant: str) -> None:
        own = (
            tenant,
            str(graph_iri(self._iris.access(tenant))),
        )  # the access record's graph is grantable
        if rule.target not in own and not self._iris.is_aggregate_graph(tenant, rule.target):
            raise InvalidGrant(
                f"{rule.target} is neither the tenant, its access record nor an aggregate graph of it"
            )
        try:
            term(URIRef(rule.assignee))
        except SparqlError as error:
            raise InvalidGrant(f"assignee {rule.assignee!r} is not an IRI: {error}") from error

    def require(
        self, caller: VerifiedCaller, access: CallerAccess, target_iri: str, action: Action
    ) -> None:
        """Raise unless ``caller`` may take ``action`` on ``target_iri``.

        ``target_iri`` is the tenant IRI for a tenant-scope action (listing, creating, administering,
        deleting the tenant), or an aggregate's root IRI (the tenant's access record included).

        Raises:
            NotFound: The target is not the tenant or one of its aggregates, the tenant is not
                active, or the caller can see nothing of the tenant or of the aggregate.
            Forbidden: A Prohibition forbids the action, or the caller may see but not take it.
        """
        scope = self._scope(access.tenant, target_iri)
        if access.state != TenantState.ACTIVE:
            raise NotFound(f"no tenant {access.tenant}")
        if self._prohibited(caller, access, scope, action):
            raise Forbidden(f"{action.value} is prohibited")
        permitted = self._permitted_actions(caller, access, scope)
        if not permitted:  # a grant that resolves to no action shows nothing
            raise NotFound(f"nothing of {target_iri} is visible to the caller")
        if not self._allows(permitted, action):
            raise Forbidden(f"{action.value} is not permitted")

    def require_application(self, caller: VerifiedCaller, action: Action) -> None:
        """Raise unless the caller's global roles permit ``action`` on the application's data (PD-9).

        The application is no tenant: it has no access record, so no grant and no prohibition is read.
        What the roles defined at level ``system`` permit is what the caller may do; any permitted
        action implies ``read``.

        Raises:
            Forbidden: The global roles permit no ``action`` here. Never ``NotFound``: that the
                application exists is no secret.
        """
        if not self._allows(self._system_actions(caller), action):
            raise Forbidden(f"{action.value} is not permitted on application data")

    def may(
        self, caller: VerifiedCaller, access: CallerAccess, target_iri: str, action: Action
    ) -> bool:
        """True when ``require`` would let ``caller`` take ``action`` on ``target_iri``."""
        try:
            self.require(caller, access, target_iri, action)
        except (NotFound, Forbidden):
            return False
        return True

    def roles(self, caller: VerifiedCaller, access: CallerAccess, target_iri: str) -> set[str]:
        """The names of the roles ``caller`` holds on ``target_iri``: its role grants in scope and those of
        its token's roles that the roles file defines at system level (a token role of another name,
        which the identity provider's administrator chose, counts for nothing; PD-30).

        Raises:
            NotFound: ``target_iri`` is not the tenant or one of its aggregates.
        """
        scope = self._scope(access.tenant, target_iri)
        granted = {
            g.role
            for g in access.grants or []
            if g.role and g.assignee == caller.principal and g.target in scope
        }
        system = {
            role for role in caller.global_roles or [] if (RoleLevel.SYSTEM, role) in self._permits
        }
        return granted | system

    def defines(self, role: str) -> bool:
        """True when a role of this name is defined at any level."""
        return any(name == role for _, name in self._permits)

    def prohibits(
        self, caller: VerifiedCaller, access: CallerAccess, target_iri: str, action: Action
    ) -> bool:
        """True when a Prohibition forbids ``caller`` ``action`` on ``target_iri`` (a ban of ``read`` forbids all).

        Raises:
            NotFound: ``target_iri`` is not the tenant or one of its aggregates.
        """
        return self._prohibited(caller, access, self._scope(access.tenant, target_iri), action)

    def allowed_actions(
        self, caller: VerifiedCaller, access: CallerAccess, target_iri: str
    ) -> list[Action]:
        """The actions of ``ACTIONS``, in that order, that the routes on ``target_iri`` allow ``caller``.

        On the tenant, ``delete`` stands for deleting the tenant, which needs ``administer`` (PD-2);
        on an aggregate no route needs ``administer``, so it is not listed (PD-10).
        """
        is_tenant = target_iri == access.tenant
        return [
            action
            for action in ACTIONS
            if self.may(caller, access, target_iri, _gate(action, is_tenant))
            and (is_tenant or action != Action.ADMINISTER)
        ]

    @staticmethod
    def hidden_graphs(caller: VerifiedCaller, access: CallerAccess) -> list[str]:
        """The graphs of the aggregates a Prohibition of ``read`` keeps from the caller, sorted.

        A listing leaves them out before it pages and counts, so a page never shows what a read of
        the same aggregate would refuse. A Prohibition of another action hides nothing.
        """
        return sorted(
            {
                p.target
                for p in access.prohibitions or []
                if p.assignee == caller.principal and p.action == Action.READ
            }
        )

    def _scope(self, tenant: str, target_iri: str) -> set[str]:
        """The targets whose rules apply to ``target_iri``: the tenant, and the aggregate's graph."""
        if target_iri == tenant:
            return {tenant}
        if not self._iris.is_aggregate(tenant, target_iri):
            raise NotFound(f"{target_iri} is not in tenant {tenant}")
        return {tenant, str(graph_iri(target_iri))}

    def _permitted_actions(
        self, caller: VerifiedCaller, access: CallerAccess, scope: set[str]
    ) -> set[Action]:
        """What the caller's grants in ``scope`` and global roles permit, before any implication."""
        grants = (
            self._granted(g, access.tenant)
            for g in access.grants or []
            if g.assignee == caller.principal and g.target in scope
        )
        return set().union(*grants, self._system_actions(caller))

    def _system_actions(self, caller: VerifiedCaller) -> set[Action]:
        """What the roles defined at level ``system`` that the caller's token carries permit."""
        return set().union(
            *(
                self._permits.get((RoleLevel.SYSTEM, role), set())
                for role in caller.global_roles or []
            )
        )

    @staticmethod
    def _allows(permitted: set[Action], action: Action) -> bool:
        """True when ``action`` is permitted, or is ``read`` and another permitted action implies it."""
        return action in permitted or (action == Action.READ and bool(permitted & _IMPLY_READ))

    @staticmethod
    def _prohibited(
        caller: VerifiedCaller, access: CallerAccess, scope: set[str], action: Action
    ) -> bool:
        """A Prohibition of ``read`` forbids every action that implies it, as well as ``read``."""
        return any(
            p.assignee == caller.principal
            and p.target in scope
            and (p.action == action or (p.action == Action.READ and action in _IMPLY_READ))
            for p in access.prohibitions or []
        )

    def _granted(self, grant: Grant, tenant: str) -> set[Action]:
        if grant.action is not None:
            return {grant.action}
        return self._permits.get((_level(grant.target, tenant), grant.role or ""), set())
