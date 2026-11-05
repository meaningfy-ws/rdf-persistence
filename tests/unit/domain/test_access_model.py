"""The access classes of the metamodel as gen-pydantic renders them.

Tests marked xfail document what gen-pydantic does not enforce from the schema (patterns it does); they feed the hard
check (task 1.6) and the shape generator (task 1.8). Each is strict: when the gap closes, it fails.
"""

import pytest
from pydantic import ValidationError

from rdf_persistence import Action, Grant, RoleLevel, StoredFile, TenantState
from tests.unit.domain.builders import grant, tenant_access

SCHEMA_ONLY = "gen-pydantic does not render this schema constraint (see tasks 1.6 and 1.8)"


@pytest.mark.parametrize(
    ("enum", "values"),
    [
        (TenantState, {"active", "deleting"}),
        (Action, {"read", "modify", "delete", "administer"}),
        (RoleLevel, {"system", "tenant", "aggregate"}),
    ],
    ids=["TenantState", "Action", "RoleLevel"],
)
def test_enum_has_exactly_the_schema_values(enum: type, values: set[str]) -> None:
    assert {member.value for member in enum} == values, f"{enum.__name__} drifted from the schema"


@pytest.mark.parametrize("state", ["active", "deleting"])
def test_tenant_access_accepts_a_known_state(state: str) -> None:
    assert tenant_access(state=state).state == TenantState(state), "the state was not kept"


def test_tenant_access_refuses_an_unknown_state() -> None:
    with pytest.raises(ValidationError):
        tenant_access(state="archived")


def test_grant_by_role_is_accepted() -> None:
    assert grant().role == "editor", "a role grant must keep its role"


def test_grant_by_action_is_accepted() -> None:
    direct = grant(role=None, action="read")
    assert direct.action == Action("read"), "a direct grant must keep its action"


@pytest.mark.parametrize("missing", ["assignee", "target"])
def test_grant_requires_assignee_and_target(missing: str) -> None:
    with pytest.raises(ValidationError, match=missing):
        Grant.model_validate(grant().model_dump(exclude={missing}))


@pytest.mark.xfail(strict=True, reason=SCHEMA_ONLY + ": exactly_one_of role and action")
def test_grant_with_both_role_and_action_is_refused() -> None:
    with pytest.raises(ValidationError):
        grant(action="read")


@pytest.mark.xfail(strict=True, reason=SCHEMA_ONLY + ": exactly_one_of role and action")
def test_grant_with_neither_role_nor_action_is_refused() -> None:
    with pytest.raises(ValidationError):
        grant(role=None)


@pytest.mark.parametrize(
    "name", ["lib-t-" + "a" * 32, "a" * 20 + "-t-" + "0123456789abcdef" * 2, "a1-t-" + "f" * 32]
)
def test_database_name_of_the_tenant_naming_rule_is_accepted(name: str) -> None:
    assert tenant_access(database_name=name).database_name == name, "the name was not kept"


@pytest.mark.parametrize(
    "name",
    [
        "acme",
        "lib-t-" + "a" * 31,
        "lib-t-" + "a" * 33,
        "lib-t-" + "A" * 32,
        "Lib-t-" + "a" * 32,
        "a" * 21 + "-t-" + "a" * 32,
        "-t-" + "a" * 32,
        "lib-system",
    ],
)
def test_database_name_outside_the_tenant_naming_rule_is_refused(name: str) -> None:
    with pytest.raises(ValidationError, match="Invalid database_name format"):
        tenant_access(database_name=name)


@pytest.mark.parametrize("label", ["", "x" * 201, "two\nlines"])
def test_tenant_label_outside_the_pattern_is_refused(label: str) -> None:
    with pytest.raises(ValidationError, match="Invalid label format"):
        tenant_access(label=label)


@pytest.mark.parametrize("label", ["x", "x" * 200])
def test_tenant_label_inside_the_pattern_is_accepted(label: str) -> None:
    assert tenant_access(label=label).label == label, "the label was not kept"


@pytest.mark.parametrize("digest", ["abc", "G" * 64, "A" * 64])
def test_stored_file_refuses_a_malformed_sha256(digest: str) -> None:
    with pytest.raises(ValidationError, match="Invalid sha256 format"):
        StoredFile(sha256=digest)


def test_stored_file_accepts_a_lowercase_hex_sha256() -> None:
    assert StoredFile(sha256="a" * 64).sha256 == "a" * 64, "the digest was not kept"


@pytest.mark.xfail(strict=True, reason=SCHEMA_ONLY + ": unique_keys grant_key")
def test_duplicate_grants_in_a_tenant_are_refused() -> None:
    with pytest.raises(ValidationError):
        tenant_access(grants=[grant(), grant()])
