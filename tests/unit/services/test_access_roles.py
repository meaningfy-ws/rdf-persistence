"""Role definitions and grant sets (PD-9, PD-10): a file is validated at start-up, a grant set before it is stored."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from rdf_persistence import Action, Grant, GrantSet, Prohibition, RoleLevel
from rdf_persistence.domain.exceptions import InvalidGrant, InvalidRoleDefinition, UnknownRole
from rdf_persistence.services.access import AccessRules, load_role_definitions
from tests.toy import ROLES, TENANT, ban, book_iri, direct, graph_of, role

BOOK = book_iri(1)
BOOK_GRAPH = graph_of(BOOK)
FOREIGN = "https://example.org/libraries/22222222-2222-4222-8222-222222222222"


def test_the_toy_librarys_role_definitions_load_as_the_design_lists_them():
    loaded = [(d.role, d.level, d.actions) for d in load_role_definitions(ROLES)]
    assert loaded == [
        ("admin", RoleLevel.SYSTEM, [Action.READ]),
        (
            "librarian",
            RoleLevel.TENANT,
            [Action.READ, Action.MODIFY, Action.DELETE, Action.ADMINISTER],
        ),
        ("reader", RoleLevel.TENANT, [Action.READ]),
        ("app-editor", RoleLevel.SYSTEM, [Action.READ, Action.MODIFY]),
    ], "the roles of PD-9 and the application editor of app-level-data PD-12, in file order"


# (id, file text, what the error must name)
REFUSED_FILES = [
    ("not-a-list", "role: admin\n", ["list"]),
    ("empty-file", "", ["list"]),
    ("entry-not-a-mapping", "- admin\n", ["entry 1"]),
    ("missing-actions", "- {role: reader, level: tenant}\n", ["entry 1", "reader", "actions"]),
    (
        "unknown-level",
        "- {role: a, level: tenant, actions: [read]}\n- {role: b, level: galaxy, actions: [read]}\n",
        ["entry 2", "b", "level"],
    ),
    ("unknown-action", "- {role: a, level: tenant, actions: [fly]}\n", ["entry 1", "a", "fly"]),
    ("missing-role", "- {level: tenant, actions: [read]}\n", ["entry 1", "role"]),
    ("not-yaml", "- {role: a\n", ["YAML"]),
    ("no-actions", "- {role: a, level: tenant, actions: []}\n", ["entry 1", "a", "actions"]),
    (
        "defined-twice-at-one-level",
        "- {role: a, level: tenant, actions: [read]}\n- {role: a, level: tenant, actions: [modify]}\n",
        ["entry 2", "a", "twice", "tenant"],
    ),
]


@pytest.mark.parametrize(
    ("text", "named"), [(t, n) for _, t, n in REFUSED_FILES], ids=[i for i, _, _ in REFUSED_FILES]
)
def test_an_invalid_role_file_is_refused_and_the_error_names_the_entry(
    tmp_path, text: str, named: list[str]
):
    path = tmp_path / "roles.yaml"
    path.write_text(text)
    with pytest.raises(InvalidRoleDefinition) as raised:
        load_role_definitions(path)
    for fragment in named:
        assert fragment in str(raised.value), f"the error should name {fragment!r}"


def test_a_missing_role_file_is_refused_with_its_path(tmp_path):
    path = tmp_path / "absent.yaml"
    with pytest.raises(InvalidRoleDefinition, match="absent.yaml"):
        load_role_definitions(path)


def test_a_role_may_be_defined_at_two_different_levels(tmp_path):
    path = tmp_path / "roles.yaml"
    path.write_text(
        "- {role: a, level: tenant, actions: [read]}\n- {role: a, level: aggregate, actions: [read]}\n"
    )
    assert len(load_role_definitions(path)) == 2


def grant_set(*grants: Grant, bans: list[Prohibition] | None = None) -> GrantSet:
    return GrantSet(grants=list(grants) or None, prohibitions=bans)


def rules() -> AccessRules:
    return AccessRules(load_role_definitions(ROLES))


def with_aggregate_roles(tmp_path) -> AccessRules:
    path = tmp_path / "roles.yaml"
    path.write_text(
        "- {role: reader, level: tenant, actions: [read]}\n"
        "- {role: curator, level: aggregate, actions: [read, modify]}\n"
        "- {role: admin, level: system, actions: [read]}\n"
    )
    return AccessRules(load_role_definitions(path))


# (id, grant, accepted?)
GRANTS = [
    ("tenant-role", role("reader"), True),
    ("another-tenant-role", role("librarian"), True),
    ("direct-action-on-an-aggregate", direct(Action.MODIFY, BOOK_GRAPH), True),
    ("direct-action-on-the-tenant", direct(Action.READ), True),
    ("direct-action-on-the-access-record", direct(Action.READ, graph_of(f"{TENANT}/access")), True),
]


@pytest.mark.parametrize(("given",), [(g,) for _, g, _ in GRANTS], ids=[i for i, _, _ in GRANTS])
def test_a_well_formed_grant_is_accepted(given: Grant):
    rules().validate_grants(grant_set(given), TENANT)


def test_a_grant_set_with_no_grants_is_valid():
    rules().validate_grants(GrantSet(), TENANT)


# (id, grant, the error)
REFUSED_GRANTS = [
    ("unknown-role", role("archivist"), UnknownRole),
    ("system-role-is-not-grantable", role("admin"), UnknownRole),
    ("tenant-role-on-an-aggregate-graph", role("reader", BOOK_GRAPH), UnknownRole),
    ("the-root-iri-is-not-the-graph", direct(Action.MODIFY, BOOK), InvalidGrant),
    (
        "a-foreign-aggregate",
        direct(Action.MODIFY, graph_of(f"{FOREIGN}/books/{UUID(int=3)}")),
        InvalidGrant,
    ),
    ("a-foreign-tenant", direct(Action.READ, FOREIGN), InvalidGrant),
    ("an-iri-outside-every-tenant", role("librarian", "https://evil.example/x"), InvalidGrant),
    (
        "an-aggregate-that-is-no-uuid",
        direct(Action.MODIFY, graph_of(f"{TENANT}/books/x")),
        InvalidGrant,
    ),
    ("the-tenant-roots-own-graph", direct(Action.MODIFY, graph_of(TENANT)), InvalidGrant),
    (
        "an-assignee-that-is-no-iri",
        Grant(assignee="not an iri", target=TENANT, role="reader"),
        InvalidGrant,
    ),
]


@pytest.mark.parametrize(
    ("given", "error"),
    [(g, e) for _, g, e in REFUSED_GRANTS],
    ids=[i for i, _, _ in REFUSED_GRANTS],
)
def test_a_grant_that_the_check_could_never_honour_is_refused(given: Grant, error):
    with pytest.raises(error):
        rules().validate_grants(grant_set(given), TENANT)


def test_the_unknown_role_error_names_the_role():
    with pytest.raises(UnknownRole, match="archivist"):
        rules().validate_grants(grant_set(role("archivist")), TENANT)


def test_an_aggregate_role_is_granted_on_an_aggregate_graph_and_not_on_the_tenant(tmp_path):
    rules_with_curator = with_aggregate_roles(tmp_path)
    rules_with_curator.validate_grants(grant_set(role("curator", BOOK_GRAPH)), TENANT)
    with pytest.raises(UnknownRole, match="curator"):
        rules_with_curator.validate_grants(grant_set(role("curator", TENANT)), TENANT)


def test_a_prohibition_is_held_to_the_same_targets_and_assignee():
    rules().validate_grants(grant_set(bans=[ban(Action.MODIFY, BOOK_GRAPH)]), TENANT)
    with pytest.raises(InvalidGrant):
        rules().validate_grants(grant_set(bans=[ban(Action.MODIFY, BOOK)]), TENANT)
    with pytest.raises(InvalidGrant):
        rules().validate_grants(grant_set(bans=[ban(Action.MODIFY, FOREIGN)]), TENANT)
    with pytest.raises(InvalidGrant):
        rules().validate_grants(grant_set(bans=[ban(Action.READ, who="not an iri")]), TENANT)


def test_two_grants_with_the_same_key_are_refused_by_the_grant_set_itself():
    with pytest.raises(ValidationError, match="grant_key"):
        grant_set(role("reader"), role("reader"))
