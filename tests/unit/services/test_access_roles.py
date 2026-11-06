"""Role definitions and grant sets (PD-9, PD-10): a file is validated at start-up, a grant set before it is stored."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence import Action, Grant, GrantSet, RoleLevel
from rdf_persistence.domain.exceptions import InvalidRoleDefinition, UnknownRole
from rdf_persistence.services.access import load_role_definitions, validate_grants
from tests.toy import ADA, TENANT, book_iri

LIBRARY_ROLES = Path(__file__).parents[2] / "fixtures" / "library" / "library_roles.yaml"
BOOK_GRAPH = f"{book_iri(1)}/graph"


def test_the_toy_librarys_role_definitions_load_as_the_design_lists_them():
    loaded = [(d.role, d.level, d.actions) for d in load_role_definitions(LIBRARY_ROLES)]
    assert loaded == [
        ("admin", RoleLevel.SYSTEM, [Action.READ]),
        (
            "librarian",
            RoleLevel.TENANT,
            [Action.READ, Action.MODIFY, Action.DELETE, Action.ADMINISTER],
        ),
        ("reader", RoleLevel.TENANT, [Action.READ]),
    ], "the three roles of PD-9, in file order"


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


def grant_set(*grants: Grant) -> GrantSet:
    return GrantSet(grants=list(grants))


def role_grant(role: str, target: str = TENANT) -> Grant:
    return Grant(assignee=ADA, target=target, role=role)


# (id, grant, accepted?)
GRANTS = [
    ("tenant-role", role_grant("reader"), True),
    ("another-tenant-role", role_grant("librarian"), True),
    ("direct-action", Grant(assignee=ADA, target=BOOK_GRAPH, action=Action.MODIFY), True),
    ("unknown-role", role_grant("archivist"), False),
    ("system-role-is-not-grantable", role_grant("admin"), False),
]


@pytest.mark.parametrize(
    ("given", "accepted"), [(g, a) for _, g, a in GRANTS], ids=[i for i, _, _ in GRANTS]
)
def test_a_grant_set_names_only_roles_the_application_defines(given: Grant, accepted: bool):
    definitions = load_role_definitions(LIBRARY_ROLES)
    if accepted:
        validate_grants(grant_set(given), definitions)
        return
    with pytest.raises(UnknownRole, match=given.role or ""):
        validate_grants(grant_set(given), definitions)


def test_a_grant_set_with_no_grants_is_valid():
    validate_grants(GrantSet(), load_role_definitions(LIBRARY_ROLES))


def test_two_grants_with_the_same_key_are_refused_by_the_grant_set_itself():
    with pytest.raises(ValidationError, match="grant_key"):
        grant_set(role_grant("reader"), role_grant("reader"))
