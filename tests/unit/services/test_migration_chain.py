"""The chain of one schema's versions, loaded from a folder of migration files (PD-4): TC-20 to TC-22."""

from pathlib import Path

import pytest
import yaml

from rdf_persistence.domain.exceptions import InvalidMigration
from rdf_persistence.services.migrations import first_version, load_chain, pending_from

SCHEMA = "https://example.org/ns/library"


def put(folder: Path, from_version: str, to_version: str, *, name: str | None = None, **fields):
    data = {"schema_id": SCHEMA, "from_version": from_version, "to_version": to_version, **fields}
    path = folder / (name or f"{from_version}__{to_version}.yaml")
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def refused(folder: Path, current: str) -> str:
    with pytest.raises(InvalidMigration) as error:
        load_chain(folder, SCHEMA, current)
    return str(error.value)


def test_files_form_one_line_in_order(tmp_path):  # TC-20
    put(tmp_path, "2", "3")
    put(tmp_path, "1", "2")
    versions, migrations = load_chain(tmp_path, SCHEMA, "3")
    assert versions == ("1", "2", "3")
    assert [(m.from_version, m.to_version) for m in migrations] == [("1", "2"), ("2", "3")]


def test_with_no_file_the_chain_is_the_current_version_alone(tmp_path):  # TC-20
    assert load_chain(tmp_path, SCHEMA, "1") == (("1",), ())


def test_the_lock_file_and_other_files_are_ignored(tmp_path):
    put(tmp_path, "1", "2")
    (tmp_path / "schema.lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.md").write_text("notes", encoding="utf-8")
    assert load_chain(tmp_path, SCHEMA, "2")[0] == ("1", "2")


def test_a_missing_folder_is_refused_naming_it(tmp_path):
    assert "nowhere" in refused(tmp_path / "nowhere", "1")


def test_a_fork_is_refused_naming_both_files(tmp_path):  # TC-21
    put(tmp_path, "1", "2")
    put(tmp_path, "1", "3")
    message = refused(tmp_path, "3")
    assert "1__2.yaml" in message and "1__3.yaml" in message


def test_two_files_reaching_one_version_are_refused(tmp_path):  # TC-21
    put(tmp_path, "1", "3")
    put(tmp_path, "2", "3")
    message = refused(tmp_path, "3")
    assert "1__3.yaml" in message and "2__3.yaml" in message


def test_a_gap_is_refused_naming_the_stranded_file(tmp_path):  # TC-21
    put(tmp_path, "1", "2")
    assert "1__2.yaml" in refused(tmp_path, "3")


def test_a_cycle_is_refused_naming_its_files(tmp_path):  # TC-21
    put(tmp_path, "1", "2")
    put(tmp_path, "2", "1")
    message = refused(tmp_path, "3")
    assert "1__2.yaml" in message and "2__1.yaml" in message


def test_a_file_leaving_the_current_version_is_refused(tmp_path):  # TC-21
    put(tmp_path, "1", "2")
    put(tmp_path, "2", "3")
    assert "2__3.yaml" in refused(tmp_path, "2")


def test_two_files_for_one_step_are_refused_naming_both(tmp_path):  # TC-21
    put(tmp_path, "1", "2")
    put(tmp_path, "1", "2", name="1__2_again.yaml")
    message = refused(tmp_path, "2")
    assert "1__2.yaml" in message and "1__2_again.yaml" in message


def test_a_foreign_schema_id_is_refused_naming_the_file(tmp_path):  # TC-21
    path = put(tmp_path, "1", "2")
    path.write_text(
        path.read_text().replace(SCHEMA, "https://example.org/ns/other"), encoding="utf-8"
    )
    assert "1__2.yaml" in refused(tmp_path, "2")


def test_a_file_name_that_differs_from_its_fields_is_refused(tmp_path):
    put(tmp_path, "1", "2", name="one_to_two.yaml")
    assert "one_to_two.yaml" in refused(tmp_path, "2")


def test_the_name_writes_each_odd_character_as_underscore(tmp_path):
    put(tmp_path, "1.0/beta", "2", name="1.0_beta__2.yaml")
    assert load_chain(tmp_path, SCHEMA, "2")[0] == ("1.0/beta", "2")


def test_a_file_that_fails_its_checks_is_refused_naming_file_and_step(tmp_path):  # TC-22
    put(tmp_path, "1", "2", steps=[{"title": "draft", "unresolved": "decide"}])
    message = refused(tmp_path, "2")
    assert "1__2.yaml" in message and "draft" in message


def test_the_first_version_and_the_pending_migrations(tmp_path):
    put(tmp_path, "1", "2")
    put(tmp_path, "2", "3")
    chain = load_chain(tmp_path, SCHEMA, "3")
    assert first_version(chain) == "1"
    assert [m.to_version for m in pending_from(chain, "1")] == ["2", "3"]
    assert [m.to_version for m in pending_from(chain, "2")] == ["3"]
    assert pending_from(chain, "3") == ()
    assert pending_from(chain, "9") is None


def test_the_first_version_of_a_chain_with_no_file_is_the_current_one():
    assert first_version((("4",), ())) == "4"
