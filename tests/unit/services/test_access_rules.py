"""The rule order of the check (PD-9, worked example step 2): each rule has a case that fires and one that does not."""

from uuid import UUID

import pytest

from rdf_persistence import Action, TenantState
from rdf_persistence.domain.exceptions import Forbidden, NotFound
from rdf_persistence.domain.iris import (
    DEFAULT_IRIS,
)
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import (
    BOB,
    ROLES,
    TENANT,
    ban,
    book_iri,
    caller,
    direct,
    graph_of,
    held,
    role,
)

BOOK = book_iri(1)
BOOK_GRAPH = graph_of(BOOK)
OTHER_GRAPH = graph_of(book_iri(2))
FOREIGN_TENANT = "https://example.org/libraries/22222222-2222-4222-8222-222222222222"
ALLOW = None
RULES = (
    "foreign-target",
    "inactive-tenant",
    "prohibition",
    "invisible",
    "permitted",
    "otherwise-forbidden",
)

# (rule, applies?, case id, caller, access, target, action, answer)
CASES = [
    (
        "inactive-tenant",
        True,
        "deleting beats a prohibition and a grant",
        caller("admin"),
        held(role("librarian"), bans=[ban(Action.READ)], state=TenantState.DELETING),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "inactive-tenant",
        False,
        "active tenant answers by the other rules",
        caller(),
        held(role("reader")),
        BOOK,
        Action.READ,
        ALLOW,
    ),
    (
        "prohibition",
        True,
        "a prohibition on the tenant blocks an aggregate",
        caller(),
        held(role("librarian"), bans=[ban(Action.MODIFY)]),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "prohibition",
        True,
        "a prohibition wins before invisibility",
        caller(),
        held(bans=[ban(Action.READ)]),
        BOOK,
        Action.READ,
        Forbidden,
    ),
    (
        "prohibition",
        True,
        "a prohibition of read blocks every action that implies read",
        caller(),
        held(role("librarian"), bans=[ban(Action.READ, BOOK_GRAPH)]),
        BOOK,
        Action.DELETE,
        Forbidden,
    ),
    (
        "prohibition",
        False,
        "a prohibition of modify leaves delete alone",
        caller(),
        held(role("librarian"), bans=[ban(Action.MODIFY)]),
        BOOK,
        Action.DELETE,
        ALLOW,
    ),
    (
        "prohibition",
        False,
        "a prohibition on another aggregate leaves this one alone",
        caller(),
        held(role("librarian"), bans=[ban(Action.MODIFY, OTHER_GRAPH)]),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "prohibition",
        False,
        "a prohibition on an aggregate does not block tenant scope",
        caller(),
        held(role("librarian"), bans=[ban(Action.MODIFY, BOOK_GRAPH)]),
        TENANT,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "prohibition",
        False,
        "another principal's prohibition is not the caller's",
        caller(),
        held(role("librarian"), bans=[ban(Action.MODIFY, who=BOB)]),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "invisible",
        True,
        "no grant, no permission, no global role",
        caller(),
        held(),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        True,
        "a global role no definition names",
        caller("root"),
        held(),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        True,
        "a tenant role in the token is not a global role",
        caller("librarian"),
        held(),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        True,
        "a grant of another principal does not show the tenant",
        caller(),
        held(role("librarian", who=BOB)),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        False,
        "a tenant grant shows the tenant",
        caller(),
        held(role("reader")),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "invisible",
        False,
        "a global role a definition names shows the tenant",
        caller("admin"),
        held(),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "permitted",
        True,
        "a role definition permits the action",
        caller(),
        held(role("librarian")),
        BOOK,
        Action.DELETE,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "modify implies read",
        caller(),
        held(direct(Action.MODIFY, BOOK_GRAPH)),
        BOOK,
        Action.READ,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "a direct permission on the aggregate permits it",
        caller(),
        held(direct(Action.DELETE, BOOK_GRAPH)),
        BOOK,
        Action.DELETE,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "a system role permits at any scope",
        caller("admin"),
        held(),
        TENANT,
        Action.READ,
        ALLOW,
    ),
    (
        "permitted",
        False,
        "a direct permission on another aggregate shows nothing",
        caller(),
        held(direct(Action.MODIFY, OTHER_GRAPH)),
        BOOK,
        Action.MODIFY,
        NotFound,
    ),
    (
        "permitted",
        False,
        "a direct tenant permission covers the tenant's aggregates",
        caller(),
        held(direct(Action.MODIFY)),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "otherwise-forbidden",
        True,
        "a reader may not modify",
        caller(),
        held(role("reader")),
        BOOK,
        Action.MODIFY,
        Forbidden,
    ),
    (
        "invisible",
        True,
        "a role no definition names permits nothing, so shows nothing",
        caller(),
        held(role("archivist")),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "invisible",
        True,
        "a system role is no tenant role, so shows nothing",
        caller(),
        held(role("admin")),
        BOOK,
        Action.READ,
        NotFound,
    ),
    (
        "otherwise-forbidden",
        False,
        "a direct permission on the aggregate does not widen a tenant role",
        caller(),
        held(role("reader"), direct(Action.MODIFY, BOOK_GRAPH)),
        BOOK,
        Action.MODIFY,
        ALLOW,
    ),
    (
        "foreign-target",
        True,
        "an aggregate of another tenant",
        caller(),
        held(role("librarian")),
        f"{FOREIGN_TENANT}/books/{UUID(int=3)}",
        Action.DELETE,
        NotFound,
    ),
    (
        "foreign-target",
        True,
        "the IRI of another tenant",
        caller(),
        held(role("librarian")),
        FOREIGN_TENANT,
        Action.ADMINISTER,
        NotFound,
    ),
    (
        "foreign-target",
        True,
        "a graph IRI is not an aggregate's root",
        caller(),
        held(direct(Action.MODIFY, BOOK_GRAPH)),
        BOOK_GRAPH,
        Action.MODIFY,
        NotFound,
    ),
    (
        "foreign-target",
        True,
        "an IRI under the tenant that is no aggregate",
        caller(),
        held(role("librarian")),
        f"{TENANT}/books/x",
        Action.READ,
        NotFound,
    ),
    (
        "foreign-target",
        False,
        "the tenant's own access record is a target",
        caller(),
        held(role("librarian")),
        str(DEFAULT_IRIS.access(TENANT)),
        Action.ADMINISTER,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "a direct delete grant on the aggregate reads it",
        caller(),
        held(direct(Action.DELETE, BOOK_GRAPH)),
        BOOK,
        Action.READ,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "a direct administer grant on the tenant reads it",
        caller(),
        held(direct(Action.ADMINISTER)),
        TENANT,
        Action.READ,
        ALLOW,
    ),
    (
        "permitted",
        True,
        "a direct read grant does not modify",
        caller(),
        held(direct(Action.READ, BOOK_GRAPH)),
        BOOK,
        Action.MODIFY,
        Forbidden,
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
        rules.require(verified_caller, access, target, action)
        return
    with pytest.raises(answer):
        rules.require(verified_caller, access, target, action)


def test_a_role_defined_at_aggregate_level_applies_to_that_aggregate_only(tmp_path):
    path = tmp_path / "roles.yaml"
    path.write_text("- {role: editor, level: aggregate, actions: [modify]}\n")
    rules = AccessRules(load_role_definitions(path))
    access = held(role("editor", BOOK_GRAPH))
    rules.require(caller(), access, BOOK, Action.MODIFY)
    with pytest.raises(NotFound):
        rules.require(caller(), access, book_iri(2), Action.MODIFY)
    with pytest.raises(NotFound):
        rules.require(caller(), access, TENANT, Action.MODIFY)


def test_an_aggregate_role_granted_on_the_tenant_shows_nothing_of_it(tmp_path):
    path = tmp_path / "roles.yaml"
    path.write_text("- {role: editor, level: aggregate, actions: [modify]}\n")
    rules = AccessRules(load_role_definitions(path))
    with pytest.raises(NotFound):
        rules.require(caller(), held(role("editor", TENANT)), TENANT, Action.READ)
