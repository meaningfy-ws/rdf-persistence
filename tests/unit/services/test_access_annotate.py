"""The ``annotate`` action and the questions a discussion asks of the rules (PD-9): roles, defines, prohibits."""

from pathlib import Path

import pytest

from rdf_persistence import Action
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ROLES, TENANT, ban, book_iri, caller, direct, graph_of, held, role

B1 = book_iri(1)
B2 = book_iri(2)
REVIEWER = "- {role: reviewer, level: tenant, actions: [read, annotate]}\n"
OWNER = "- {role: owner, level: aggregate, actions: [read, modify]}\n"


@pytest.fixture
def rules(tmp_path: Path) -> AccessRules:
    """The toy library's roles, a tenant ``reviewer`` that may read and annotate, and an aggregate ``owner``."""
    path = tmp_path / "roles.yaml"
    path.write_text(ROLES.read_text() + REVIEWER + OWNER)
    return AccessRules(load_role_definitions(path))


def test_a_reviewer_may_annotate_but_not_modify(rules: AccessRules) -> None:
    """TC-41"""
    who, access = caller(), held(role("reviewer"))
    assert rules.may(who, access, B1, Action.ANNOTATE), "reviewer names annotate"
    assert not rules.may(who, access, B1, Action.MODIFY), "reviewer does not name modify"


def test_a_role_that_does_not_name_annotate_does_not_allow_it(rules: AccessRules) -> None:
    """TC-42"""
    assert not rules.may(caller(), held(role("librarian")), B1, Action.ANNOTATE)


def test_a_direct_annotate_permission_implies_read(rules: AccessRules) -> None:
    """TC-43"""
    who, access = caller(), held(direct(Action.ANNOTATE))
    assert rules.may(who, access, B1, Action.READ), "annotate implies read"
    assert not rules.may(who, access, B1, Action.MODIFY), "and nothing else"


def test_annotate_is_the_last_action_so_the_order_of_the_others_is_kept() -> None:
    assert list(Action)[-1] == Action.ANNOTATE
    assert [a.value for a in Action][:4] == ["read", "modify", "delete", "administer"]


def test_the_roles_of_a_caller_are_its_grants_in_scope_and_its_global_roles(
    rules: AccessRules,
) -> None:
    """TC-44"""
    access = held(role("reader"), role("owner", graph_of(B1)), role("owner", graph_of(B2)))
    who = caller("admin")
    assert rules.roles(who, access, B1) == {"reader", "owner", "admin"}
    only_reader = held(role("reader"), role("owner", graph_of(B1)))
    assert rules.roles(who, only_reader, B2) == {"reader", "admin"}, "b1's role is not b2's"


def test_a_direct_grant_has_no_role_and_a_tenant_target_sees_tenant_grants_only(
    rules: AccessRules,
) -> None:
    access = held(direct(Action.READ), role("reader"), role("owner", graph_of(B1)))
    assert rules.roles(caller(), access, TENANT) == {"reader"}


@pytest.mark.parametrize(
    ("role_name", "defined"),
    [("reader", True), ("owner", True), ("reviewer", True), ("admin", True), ("nobody", False)],
)
def test_a_role_is_defined_at_any_level(rules: AccessRules, role_name: str, defined: bool) -> None:
    assert rules.defines(role_name) is defined


def test_prohibits_tells_a_ban_on_the_aggregate_or_the_tenant_from_none(rules: AccessRules) -> None:
    """TC-44a"""
    who = caller()
    on_graph = held(role("librarian"), bans=[ban(Action.MODIFY, graph_of(B1))])
    on_tenant = held(role("librarian"), bans=[ban(Action.MODIFY)])
    assert rules.prohibits(who, on_graph, B1, Action.MODIFY)
    assert rules.prohibits(who, on_tenant, B1, Action.MODIFY)
    assert not rules.prohibits(who, held(role("librarian")), B1, Action.MODIFY)
    assert not rules.prohibits(who, on_graph, B2, Action.MODIFY), "a ban on b1 is not one on b2"
