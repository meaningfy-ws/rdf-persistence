"""``grant_roles`` of a migration file: how it is loaded and checked, and the request built from it (grant-roles D-1 to D-4).

T5 (a request that is not for the system database has no grant operation) and T6 (the load checks) of the
change; the effect of the operations on stored grants is proved in ``tests/unit/tenancy/test_migrate_dataset.py``.
"""

from pathlib import Path

import pytest
from rdflib.plugins.sparql.parser import parseUpdate

from rdf_persistence.core.domain.exceptions import InvalidMigration
from rdf_persistence.migrations.services.generated.rp_migrations_services import (
    GrantRoles,
    Migration,
    RoleRename,
)
from rdf_persistence.migrations.services.migrations import load_migration, migration_request
from rdf_persistence.schema.services import vocabulary as v
from tests.unit.migrations.migration_steps import FILE, SCHEMA, STAMPS, rename

HEADER = f"schema_id: {SCHEMA}\nfrom_version: '1'\nto_version: '2'\n"
ROLE = str(v.ROLE)


def loaded(tmp_path: Path, body: str) -> Migration:
    path = tmp_path / FILE
    path.write_text(HEADER + body, encoding="utf-8")
    return load_migration(path)


def refusal(tmp_path: Path, body: str) -> str:
    path = tmp_path / FILE
    path.write_text(HEADER + body, encoding="utf-8")
    with pytest.raises(InvalidMigration) as refused:
        load_migration(path)
    assert str(path) in str(refused.value), "the message names the file"
    return str(refused.value)


def roles(
    rename_pairs: list[tuple[str, str]] | None = None, drop: list[str] | None = None
) -> GrantRoles:
    renames = [RoleRename(from_role=a, to_role=b) for a, b in rename_pairs or []]
    return GrantRoles(rename=renames or None, drop=drop)


def with_roles(grant_roles: GrantRoles | None, *steps) -> Migration:
    return Migration(
        schema_id=SCHEMA,
        from_version="1",
        to_version="2",
        steps=list(steps) or None,
        grant_roles=grant_roles,
    )


def operations(request: str) -> list[str]:
    """The operations of a request as text (the request joins them with a semicolon and a newline)."""
    return request.split(";\n")


def count(request: str) -> int:
    return len(parseUpdate(request).request)


# -- T6: the load map and the load checks (D-1, D-2) ---------------------------------------------------


def test_a_rename_map_is_loaded_as_the_list_in_file_order(tmp_path):
    migration = loaded(
        tmp_path, "grant_roles:\n  rename: {reader: member, viewer: member}\n  drop: [guest]\n"
    )
    assert migration.grant_roles == roles(
        [("reader", "member"), ("viewer", "member")], ["guest"]
    ), "the map is the list of its pairs, in the order of the file"


@pytest.mark.parametrize(
    "body",
    [
        "grant_roles:\n  rename: {reader: member}\n",
        "grant_roles:\n  drop: [guest]\n",
        "grant_roles:\n  rename: {reader: member}\n  drop: [guest]\n",
        "grant_roles:\n  rename: {reader: member, viewer: member}\n",
        "grant_roles: {}\n",
        "grant_roles:\n  rename: [{from_role: reader, to_role: member}]\n",
        "grant_roles:\n  drop: [guest, guest]\n",
    ],
    ids=["rename", "drop", "both", "a merge", "empty", "the list form", "a name dropped twice"],
)
def test_a_file_with_only_grant_roles_loads_and_its_request_parses(tmp_path, body):
    migration = loaded(tmp_path, body)
    request = migration_request(migration, STAMPS, grants=True)
    expected = len(migration.grant_roles.rename or []) * 2 + len(migration.grant_roles.drop or [])
    expected += 2 if expected else 1  # the rotation, if any, and the stamp move
    assert count(request) == expected, (
        "the request parses into the grant operations, the rotation, the stamp move"
    )


@pytest.mark.parametrize(
    ("body", "named"),
    [
        ("grant_roles:\n  rename: {reader: member}\n  drop: [reader]\n", "reader"),
        ("grant_roles:\n  rename: {reader: member}\n  drop: [member]\n", "member"),
        ("grant_roles:\n  rename: {reader: member, member: owner}\n", "member"),
        ("grant_roles:\n  rename: {reader: reader}\n", "reader"),
        ("grant_roles:\n  rename: {'': member}\n", "empty"),
        ("grant_roles:\n  rename: {reader: ''}\n", "empty"),
        ("grant_roles:\n  rename: {reader: ' '}\n", "empty"),
        ("grant_roles:\n  drop: ['']\n", "empty"),
        (
            "grant_roles:\n  rename: [{from_role: reader, to_role: a}, {from_role: reader, to_role: b}]\n",
            "reader",
        ),
        ("grant_roles:\n  rename: {a\\u00e9: b}\n", "codepoint"),
    ],
    ids=[
        "dropped and renamed from",
        "dropped and renamed to",
        "a chain",
        "a rename to itself",
        "an empty source",
        "an empty target",
        "a blank target",
        "an empty drop",
        "one source renamed twice",
        "a codepoint escape",
    ],
)
def test_a_file_that_contradicts_itself_is_refused_naming_the_file(tmp_path, body, named):
    assert named in refusal(tmp_path, body), "the message says what is wrong"


@pytest.mark.parametrize(
    "body",
    [
        "grant_roles:\n  rename: [reader]\n",
        "grant_roles:\n  rename: {reader: [member]}\n",
        "grant_roles:\n  drop: guest\n",
        "grant_roles: [reader]\n",
        "grant_roles:\n  rename: {reader: member}\n  other: 1\n",
    ],
    ids=[
        "a bare list",
        "a list as target",
        "drop as text",
        "grant_roles as a list",
        "an unknown key",
    ],
)
def test_a_grant_roles_of_the_wrong_shape_is_refused_naming_the_file(tmp_path, body):
    refusal(tmp_path, body)


# -- T5 and D-3: the grants flag ------------------------------------------------------------------------


def test_a_request_built_without_the_flag_has_no_grant_operation(tmp_path):
    migration = with_roles(roles([("reader", "member")], ["guest"]), rename())
    plain = with_roles(None, rename())
    assert migration_request(migration, STAMPS) == migration_request(plain, STAMPS), (
        "the default is the request of the file without grant_roles, byte for byte"
    )
    assert migration_request(migration, STAMPS, grants=False) == migration_request(plain, STAMPS), (
        "the flag false is the default"
    )
    assert ROLE not in migration_request(migration, STAMPS), "no operation touches the grants' role"


def test_a_grant_only_migration_without_the_flag_moves_only_the_stamp():
    migration = with_roles(roles([("reader", "member")], ["guest"]))
    assert count(migration_request(migration, STAMPS)) == 1, "the stamp move alone, and no rotation"


def test_a_request_with_the_flag_and_no_grant_roles_is_as_without_it():
    migration = with_roles(None, rename())
    assert migration_request(migration, STAMPS, grants=True) == migration_request(
        migration, STAMPS
    ), "a file with no grant_roles has nothing to add"


def test_the_grant_operations_follow_the_steps_and_come_before_the_rotation():
    migration = with_roles(roles([("reader", "member")], ["guest"]), rename())
    ops = operations(migration_request(migration, STAMPS, grants=True))
    assert len(ops) == 1 + 2 + 1 + 1 + 1, (
        "a step, two for the rename, one drop, the rotation, the stamp move"
    )
    assert ROLE not in ops[0], "the step comes first"
    assert all(ROLE in op for op in ops[1:4]), "then the grant operations"
    assert "STRUUID" in ops[4], "then the rotation"
    assert ROLE not in ops[5], "and the stamp move last"


def test_a_grant_only_migration_with_the_flag_rotates_the_tokens():
    migration = with_roles(roles(drop=["guest"]))
    ops = operations(migration_request(migration, STAMPS, grants=True))
    assert len(ops) == 3, "the drop, the rotation, the stamp move"
    assert "STRUUID" in ops[1], "a grant operation changes a graph, so the tokens rotate"


def test_the_operations_run_rename_by_rename_then_the_drops_last():
    """D-4: the order keeps a merge from leaving duplicates, so it is the order of the file."""
    migration = with_roles(roles([("reader", "member"), ("viewer", "member")], ["guest"]))
    ops = operations(migration_request(migration, STAMPS, grants=True))[:5]
    named = [
        {name for name in ("reader", "viewer", "guest", "member") if f'"{name}"' in op}
        for op in ops
    ]
    assert named == [
        {"reader", "member"},
        {"reader", "member"},
        {"viewer", "member"},
        {"viewer", "member"},
        {"guest"},
    ], "the first rename (both operations), the second rename (both), then the drop"
    inserts = ["INSERT" in op for op in ops]
    assert inserts == [False, True, False, True, False], (
        "of each rename, the removal of the duplicate, then the rename"
    )


def test_every_grant_operation_keeps_the_stamp_guard_and_the_graph_exclusions():
    migration = with_roles(roles([("reader", "member")], ["guest"]))
    ops = operations(migration_request(migration, STAMPS, grants=True))[:3]
    for op in ops:
        assert "FILTER (?rp_graph !=" in op, "the stamps graph is not touched"
        assert "MINUS" in op, "a loaded graph is not touched"
        assert "FILTER NOT EXISTS" in op, "a registry graph is not touched"
        assert '"1"' in op, "the from_version stamp guards the operation"


@pytest.mark.parametrize(
    "name",
    ['a" } ; DROP ALL ; { "', "a\\", "line\nbreak", "café", "'; DELETE WHERE { ?s ?p ?o } #"],
    ids=["a quote and braces", "a backslash", "a newline", "non-ascii", "a single quote"],
)
def test_a_role_name_is_a_literal_and_never_changes_the_shape_of_the_request(name):
    migration = with_roles(roles([(name, "member")], [name + "x"]))
    request = migration_request(migration, STAMPS, grants=True)
    assert count(request) == 2 + 1 + 1 + 1, (
        "two for the rename, a drop, the rotation, the stamp move"
    )
