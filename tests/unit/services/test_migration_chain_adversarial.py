"""Attacks on the chain of one schema's migration files (PD-4): odd versions, odd folders, long chains."""

import os
from pathlib import Path

import pytest
import yaml

from rdf_persistence.domain.exceptions import InvalidMigration
from rdf_persistence.services.migrations import first_version, load_chain, pending_from
from tests.unit.services.test_migration_chain import SCHEMA, put, refused


def name_of(version: str) -> str:
    """The file-name form of a version, written here from PD-4 and not from the code under test."""
    return "".join(c if c.isascii() and (c.isalnum() or c in ".-") else "_" for c in version)


def chain_of(folder: Path, versions: list[str]) -> None:
    """One file per step of ``versions``, named as PD-4 says."""
    for old, new in zip(versions, versions[1:], strict=False):
        put(folder, old, new, name=f"{name_of(old)}__{name_of(new)}.yaml")


# -- odd versions --------------------------------------------------------------------------------

ODD = {
    "with spaces": ["a b", "c d", "e f"],
    "a slash": ["1/0", "1/1", "2/0"],
    "a dot and dash": ["1.0-rc.1", "1.0", "1.0.1"],
    "unicode": ["café", "naïve", "中文"],
    "double underscores": ["a__b", "c__d", "e"],
    "quotes and colons": ['q"1', "q:2", "q'3"],
    "newlines": ["1\n", "2\n", "3\n"],
    "starting with a dash": ["-1", "-2", "-3"],
    "dots only": [".", "..", "..."],
    "very long": ["v" * 100, "w" * 100, "x" * 100],
    "numeric look": ["1", "01", "1.0"],
}


@pytest.mark.parametrize("versions", ODD.values(), ids=ODD)
def test_odd_versions_form_a_chain_in_order(tmp_path, versions):
    chain_of(tmp_path, versions)
    chain = load_chain(tmp_path, SCHEMA, versions[-1])
    assert chain[0] == tuple(versions)
    assert first_version(chain) == versions[0]
    assert [m.to_version for m in pending_from(chain, versions[0])] == versions[1:]
    assert pending_from(chain, versions[-1]) == ()


def test_versions_that_collide_after_the_file_name_mapping_are_still_told_apart(tmp_path):
    """``1/0`` and ``1_0`` are two versions with one spelling in a file name; the fields are the truth."""
    chain_of(tmp_path, ["1_0", "1/0", "2"])
    chain = load_chain(tmp_path, SCHEMA, "2")
    assert chain[0] == ("1_0", "1/0", "2")


def test_two_files_whose_versions_collide_in_the_name_cannot_both_exist_and_none_is_lost(tmp_path):
    put(tmp_path, "1/0", "2", name="1_0__2.yaml")
    put(tmp_path, "1_0", "2", name="1_0__2_b.yaml")
    message = refused(tmp_path, "2")
    assert "1_0__2.yaml" in message and "1_0__2_b.yaml" in message


def test_a_file_named_for_another_spelling_of_the_same_versions_is_refused(tmp_path):
    put(tmp_path, "1/0", "2", name="1.0__2.yaml")
    assert "1.0__2.yaml" in refused(tmp_path, "2")


def test_the_empty_version_is_a_version_or_a_clean_refusal(tmp_path):
    put(tmp_path, "", "1", name="__1.yaml")
    try:
        chain = load_chain(tmp_path, SCHEMA, "1")
    except InvalidMigration:
        return
    assert chain[0] == ("", "1")
    assert first_version(chain) == ""
    assert pending_from(chain, "") is not None


@pytest.mark.parametrize("version", ["", " ", "x", "1 "])
def test_a_version_not_in_the_chain_has_no_pending_migrations(tmp_path, version):
    chain_of(tmp_path, ["1", "2", "3"])
    assert pending_from(load_chain(tmp_path, SCHEMA, "3"), version) is None


def test_a_current_version_that_is_not_an_exact_spelling_of_the_last_file_is_a_gap(tmp_path):
    chain_of(tmp_path, ["1", "2"])
    assert "1__2.yaml" in refused(tmp_path, "2 ")
    assert "1__2.yaml" in refused(tmp_path, "02")


# -- from == to, cycles, forks -------------------------------------------------------------------


def test_a_file_that_goes_from_a_version_to_itself_is_refused_whatever_current_is(tmp_path):
    put(tmp_path, "1", "1")
    for current in ("1", "2", ""):
        assert "1__1.yaml" in refused(tmp_path, current)


def test_a_self_step_in_the_middle_of_a_line_is_refused(tmp_path):
    chain_of(tmp_path, ["1", "2"])
    put(tmp_path, "2", "2")
    put(tmp_path, "2", "3")
    assert "2__2.yaml" in refused(tmp_path, "3")


def test_a_long_cycle_beside_a_line_is_refused_and_the_loop_ends(tmp_path):
    chain_of(tmp_path, ["1", "2", "3"])
    cycle = ["a", "b", "c", "d", "a"]
    chain_of(tmp_path, cycle)
    message = refused(tmp_path, "3")
    assert "a__b.yaml" in message and "d__a.yaml" in message


def test_a_cycle_through_the_current_version_is_refused_and_the_loop_ends(tmp_path):
    chain_of(tmp_path, ["1", "2", "3", "1"])
    refused(tmp_path, "3")


def test_a_cycle_that_does_not_contain_current_but_leads_into_it_is_refused(tmp_path):
    chain_of(tmp_path, ["1", "2", "1"])
    put(tmp_path, "2", "3")
    refused(tmp_path, "3")


def test_a_fork_made_of_two_spellings_is_a_fork(tmp_path):
    put(tmp_path, "1", "2")
    put(tmp_path, "1", "2.0")
    message = refused(tmp_path, "2")
    assert "1__2.yaml" in message and "1__2.0.yaml" in message


# -- folders, files, links -----------------------------------------------------------------------


def test_a_sub_folder_with_migrations_is_not_read(tmp_path):
    chain_of(tmp_path, ["1", "2"])
    sub = tmp_path / "archive"
    sub.mkdir()
    put(sub, "0", "1")
    put(sub, "9", "10")
    assert load_chain(tmp_path, SCHEMA, "2")[0] == ("1", "2")


def test_a_folder_named_like_a_migration_is_refused_cleanly_or_ignored(tmp_path):
    chain_of(tmp_path, ["1", "2"])
    (tmp_path / "old.yaml").mkdir()
    try:
        chain = load_chain(tmp_path, SCHEMA, "2")
    except InvalidMigration as error:
        assert "old.yaml" in str(error)
    else:
        assert chain[0] == ("1", "2")


def test_other_extensions_are_not_migrations(tmp_path):
    """Only ``*.yaml`` is read (PD-4); a file the loader skips cannot take part in the chain."""
    chain_of(tmp_path, ["1", "2"])
    put(tmp_path, "2", "3", name="2__3.yml")
    put(tmp_path, "3", "4", name="3__4.YAML")
    put(tmp_path, "4", "5", name="4__5.yaml.bak")
    put(tmp_path, "5", "6", name="5__6")
    assert load_chain(tmp_path, SCHEMA, "2")[0] == ("1", "2")


def test_a_skipped_file_leaves_a_visible_gap_when_the_chain_needs_it(tmp_path):
    chain_of(tmp_path, ["1", "2"])
    put(tmp_path, "2", "3", name="2__3.yml")
    assert "1__2.yaml" in refused(tmp_path, "3")


def test_a_hidden_file_named_yaml_is_read(tmp_path):
    put(tmp_path, "1", "2", name=".1__2.yaml")
    assert ".1__2.yaml" in refused(tmp_path, "2"), "its name is not <from>__<to>.yaml"


def test_a_link_to_a_migration_is_a_second_file_for_the_same_step(tmp_path):
    original = put(tmp_path, "1", "2")
    os.symlink(original, tmp_path / "1__2_link.yaml")
    message = refused(tmp_path, "2")
    assert "1__2.yaml" in message and "1__2_link.yaml" in message


def test_a_link_to_a_migration_outside_the_folder_is_read(tmp_path):
    outside = tmp_path / "outside"
    folder = tmp_path / "migrations"
    outside.mkdir()
    folder.mkdir()
    target = put(outside, "1", "2")
    os.symlink(target, folder / "1__2.yaml")
    assert load_chain(folder, SCHEMA, "2")[0] == ("1", "2")


@pytest.mark.parametrize("kind", ["broken", "loop"])
def test_a_link_that_leads_nowhere_is_refused_naming_it(tmp_path, kind):
    link = tmp_path / "1__2.yaml"
    os.symlink(tmp_path / ("gone.yaml" if kind == "broken" else "1__2.yaml"), link)
    assert "1__2.yaml" in refused(tmp_path, "2")


def test_a_folder_that_is_a_file_is_refused_naming_it(tmp_path):
    path = tmp_path / "migrations"
    path.write_text("x", encoding="utf-8")
    assert "migrations" in refused(path, "1")


@pytest.mark.parametrize(
    "content",
    [b"\xff\xfe\x00\x00", b"schema_id: \xc3\x28", b"\x80\x81"],
    ids=["utf16-noise", "bad-continuation", "stray-bytes"],
)
def test_a_file_that_is_not_utf8_is_refused_naming_it(tmp_path, content):
    chain_of(tmp_path, ["1", "2"])
    (tmp_path / "2__3.yaml").write_bytes(content)
    message = refused(tmp_path, "3")
    assert "2__3.yaml" in message


def test_an_empty_yaml_file_is_refused_naming_it(tmp_path):
    chain_of(tmp_path, ["1", "2"])
    (tmp_path / "2__3.yaml").write_text("", encoding="utf-8")
    assert "2__3.yaml" in refused(tmp_path, "3")


def test_a_file_for_another_schema_poisons_the_folder_whatever_its_name(tmp_path):
    chain_of(tmp_path, ["1", "2"])
    data = {"schema_id": "https://example.org/ns/other", "from_version": "7", "to_version": "8"}
    (tmp_path / "7__8.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    assert "7__8.yaml" in refused(tmp_path, "2")


def test_the_same_files_give_the_same_chain_whatever_the_order_they_are_listed(tmp_path):
    versions = [str(i) for i in range(1, 12)]
    for old, new in reversed(list(zip(versions, versions[1:], strict=False))):
        put(tmp_path, old, new)
    assert load_chain(tmp_path, SCHEMA, versions[-1])[0] == tuple(versions)


# -- length --------------------------------------------------------------------------------------


def test_a_chain_of_several_hundred_files_loads_in_order_without_recursion(tmp_path):
    count = 300
    versions = [f"v{i}" for i in range(count + 1)]
    chain_of(tmp_path, versions)
    chain = load_chain(tmp_path, SCHEMA, versions[-1])
    assert chain[0] == tuple(versions)
    assert len(chain[1]) == count
    assert [m.from_version for m in pending_from(chain, "v290")] == versions[290:-1]


def test_a_long_cycle_of_several_hundred_files_ends_in_a_refusal(tmp_path):
    versions = [f"v{i}" for i in range(100)]
    chain_of(tmp_path, [*versions, versions[0]])
    refused(tmp_path, versions[-1])


def test_a_long_fork_is_refused_naming_both_files(tmp_path):
    chain_of(tmp_path, [f"v{i}" for i in range(100)])
    put(tmp_path, "v50", "side")
    message = refused(tmp_path, "v99")
    assert "v50__v51.yaml" in message and "v50__side.yaml" in message


def test_pending_from_does_not_mutate_or_alias_the_chain(tmp_path):
    chain_of(tmp_path, ["1", "2", "3"])
    chain = load_chain(tmp_path, SCHEMA, "3")
    first = pending_from(chain, "1")
    assert first == pending_from(chain, "1")
    assert isinstance(first, tuple)
    assert chain[0] == ("1", "2", "3")
