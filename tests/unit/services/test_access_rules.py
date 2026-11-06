"""The rule order of the check (PD-9, worked example step 2): each rule has a case that fires and one that does not."""

from pathlib import Path

import pytest

from rdf_persistence import Action, Grant, Prohibition, TenantState, VerifiedCaller
from rdf_persistence.domain.exceptions import Forbidden, NotFound
from rdf_persistence.domain.generated.service.rp_service import CallerAccess
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ADA, TENANT, book_iri

ROLES = Path(__file__).parents[2] / "fixtures" / "library" / "library_roles.yaml"
BOB = "https://example.org/people/bob"
BOOK = book_iri(1)
BOOK_GRAPH = f"{BOOK}/graph"
OTHER_GRAPH = f"{book_iri(2)}/graph"
ALLOW = None
RULES = ("inactive-tenant", "prohibition", "invisible", "permitted", "otherwise-forbidden")


def verified(*global_roles: str) -> VerifiedCaller:
    return VerifiedCaller(principal=ADA, global_roles=list(global_roles) or None)


def role(name: str, target: str = TENANT, who: str = ADA) -> Grant:
    return Grant(assignee=who, target=target, role=name)


def ban(action: Action, target: str = TENANT, who: str = ADA) -> Prohibition:
    return Prohibition(assignee=who, target=target, action=action)


def held(
    *grants: Grant, bans: list[Prohibition] | None = None, state=TenantState.ACTIVE
) -> CallerAccess:
    return CallerAccess(tenant=TENANT, state=state, grants=list(grants) or None, prohibitions=bans)


# (rule, applies?, case id, caller, access, target, action, answer)
CASES = [
    (
        "inactive-tenant",
        True,
        "deleting beats a prohibition and a grant",
        verified("admin"),
        held(role("librarian"), bans=[ban(Action.READ)], state=TenantState.DELETING),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "inactive-tenant",
        False,
        "active tenant answers by the other rules",
        verified(),
        held(role("reader")),
        BOOK,
        Action.READ,
        ALLOW,
    ),
    (
        "prohibition",
        True,
        "a prohibition on the tenant blocks an aggregate",
        verified(),
        held(role("librarian"), bans=[ban(Action.MODIFY)]),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "prohibition",
        True,
        "a prohibition wins before invisibility",
        verified(),
        held(bans=[ban(Action.READ)]),
        BOOK,
        Action.READ,
        Forbidden,
    ),
    (
        "prohibition",
        True,
        "a prohibition of read blocks every action that implies read",
        verified(),
        held(role("librarian"), bans=[ban(Action.READ, BOOK_GRAPH)]),
        BOOK,
        Action.DELETE,
        Forbidden,
    ),
    (
        "prohibition",
        False,
        "a prohibition of modify leaves delete alone",
        verified(),
        held(role("librarian"), bans=[ban(Action.MODIFY)]),
        BOOK,
        Action.DELETE,
        ALLOW,
    ),
    (
        "prohibition",
        False,
        "a prohibition on another aggregate leaves this one alone",
        verified(),
        held(role("librarian"), bans=[ban(Action.MODIFY, OTHER_GRAPH)]),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "prohibition",
        False,
        "a prohibition on an aggregate does not block tenant scope",
        verified(),
        held(role("librarian"), bans=[ban(Action.MODIFY, BOOK_GRAPH)]),
        TENANT,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "prohibition",
        False,
        "another principal's prohibition is not the caller's",
        verified(),
        held(role("librarian"), bans=[ban(Action.MODIFY, who=BOB)]),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "invisible",
        True,
        "no grant, no permission, no global role",
        verified(),
        held(),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        True,
        "a global role no definition names",
        verified("root"),
        held(),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        True,
        "a tenant role in the token is not a global role",
        verified("librarian"),
        held(),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        True,
        "a grant of another principal does not show the tenant",
        verified(),
        held(role("librarian", who=BOB)),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        False,
        "a tenant grant shows the tenant",
        verified(),
        held(role("reader")),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "invisible",
        False,
        "a global role a definition names shows the tenant",
        verified("admin"),
        held(),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "permitted",
        True,
        "a role definition permits the action",
        verified(),
        held(role("librarian")),
        BOOK,
        Action.DELETE,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "modify implies read",
        verified(),
        held(Grant(assignee=ADA, target=BOOK_GRAPH, action=Action.MODIFY)),
        BOOK,
        Action.READ,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "a direct permission on the aggregate permits it",
        verified(),
        held(Grant(assignee=ADA, target=BOOK_GRAPH, action=Action.DELETE)),
        BOOK,
        Action.DELETE,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "a system role permits at any scope",
        verified("admin"),
        held(),
        TENANT,
        Action.READ,
        ALLOW,
    ),
    (
        "permitted",
        False,
        "a direct permission on another aggregate shows nothing",
        verified(),
        held(Grant(assignee=ADA, target=OTHER_GRAPH, action=Action.MODIFY)),
        BOOK,
        Action.MODIFY,
        NotFound,
    ),
    (
        "permitted",
        False,
        "a direct tenant permission covers the tenant's aggregates",
        verified(),
        held(Grant(assignee=ADA, target=TENANT, action=Action.MODIFY)),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "otherwise-forbidden",
        True,
        "a reader may not modify",
        verified(),
        held(role("reader")),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "otherwise-forbidden",
        True,
        "a role no definition names permits nothing",
        verified(),
        held(role("archivist")),
        BOOK,
        Action.READ,
        Forbidden,
    ),
    (
        "otherwise-forbidden",
        True,
        "a system role is no tenant role",
        verified(),
        held(role("admin")),
        BOOK,
        Action.READ,
        Forbidden,
    ),
    (
        "otherwise-forbidden",
        False,
        "a direct permission on the aggregate does not widen a tenant role",
        verified(),
        held(role("reader"), Grant(assignee=ADA, target=BOOK_GRAPH, action=Action.MODIFY)),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
]


def test_every_rule_of_the_check_has_a_case_that_fires_and_a_case_that_does_not():
    seen = {(rule, applies) for rule, applies, *_ in CASES}
    assert seen == {(rule, applies) for rule in RULES for applies in (True, False)}, (
        "a rule lacks a case"
    )


@pytest.mark.parametrize(
    ("verified_caller", "access", "target", "action", "answer"),
    [case[3:] for case in CASES],
    ids=[f"{case[0]}-{'fires' if case[1] else 'idle'}: {case[2]}" for case in CASES],
)
def test_each_rule_case(verified_caller, access, target, action, answer):
    rules = AccessRules(load_role_definitions(ROLES))
    if answer is ALLOW:
        rules.allowed(verified_caller, access, target, action)
        return
    with pytest.raises(answer):
        rules.allowed(verified_caller, access, target, action)


def test_a_role_defined_at_aggregate_level_applies_to_that_aggregate_only(tmp_path):
    path = tmp_path / "roles.yaml"
    path.write_text("- {role: editor, level: aggregate, actions: [modify]}\n")
    rules = AccessRules(load_role_definitions(path))
    access = held(role("editor", BOOK_GRAPH))
    rules.allowed(verified(), access, BOOK, Action.MODIFY)
    with pytest.raises(NotFound):
        rules.allowed(verified(), access, book_iri(2), Action.MODIFY)
    with pytest.raises(NotFound):
        rules.allowed(verified(), access, TENANT, Action.MODIFY)
