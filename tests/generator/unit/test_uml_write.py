"""TC-10 (write part): the files, the sorted report, the stale-file line, the byte-identical rerun (PD-22, I-2)."""

from pathlib import Path

import pytest
import yaml
from linkml_runtime.linkml_model.meta import SchemaDefinition

from rdf_persistence.access.services.access import load_role_definitions
from rdf_persistence.core.domain.exceptions import InvalidRoleDefinition
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    ReportKind,
    ReportLine,
)
from rdf_persistence_generation.problems import format_problem, format_problems
from rdf_persistence_generation.uml import write as write_module
from rdf_persistence_generation.uml.write import StagedFileRefused, write
from tests.generator.uml_model import BOOK, Converted, klass, model, object_, run

ROOT = "lib"
ROLES_FILE = f"{ROOT}.roles.yaml"
ROLE_DEFINITION = 30  # the drawn toolkit class rp:RoleDefinition


def _schemas() -> list[SchemaDefinition]:
    return [
        SchemaDefinition(id="https://example.org/ns/library", name="lib_books"),
        SchemaDefinition(id="https://example.org/ns/shelves", name="lib_shelves"),
    ]


def _report() -> list[ReportLine]:
    return [
        ReportLine(report_kind=ReportKind.NOT_GENERATED, element="lib:Shelf", message="stereotype"),
        ReportLine(report_kind=ReportKind.NO_NOTE, element="lib:Book", message="no note"),
    ]


def _files(folder: Path) -> dict[str, bytes]:
    return {file.name: file.read_bytes() for file in sorted(folder.iterdir())}


def test_each_schema_and_the_report_are_written(tmp_path: Path) -> None:
    write(_schemas(), _report(), tmp_path, ROOT)

    files = _files(tmp_path)
    assert sorted(files) == [
        "lib.uml-report.txt",
        "lib_books.yaml",
        "lib_shelves.yaml",
    ], f"one file per schema and the report: {sorted(files)}"
    assert b"name: lib_books" in files["lib_books.yaml"], "lib_books.yaml holds the books schema"
    assert b"name: lib_shelves" in files["lib_shelves.yaml"], "lib_shelves.yaml holds shelves"


def test_the_report_is_sorted_and_prints_kinds_with_a_dash(tmp_path: Path) -> None:
    write(_schemas(), _report(), tmp_path, ROOT)

    text = (tmp_path / "lib.uml-report.txt").read_text(encoding="utf-8")
    assert text == "no-note\tlib:Book\tno note\nnot-generated\tlib:Shelf\tstereotype\n", repr(text)


def test_a_second_run_is_byte_identical(tmp_path: Path) -> None:
    write(_schemas(), _report(), tmp_path, ROOT)
    first = _files(tmp_path)

    write(_schemas(), list(reversed(_report())), tmp_path, ROOT)

    assert _files(tmp_path) == first, (
        "the second run, even with the report reversed, changes no byte"
    )


def test_a_file_this_run_did_not_write_is_kept_and_reported_stale(tmp_path: Path) -> None:
    (tmp_path / "lib_old.yaml").write_text("name: lib_old\n", encoding="utf-8")

    added = write(_schemas(), _report(), tmp_path, ROOT)

    assert (tmp_path / "lib_old.yaml").read_text(encoding="utf-8") == "name: lib_old\n", (
        "the stale file is kept as it was"
    )
    assert [(line.report_kind, line.element) for line in added] == [
        (ReportKind.STALE_FILE, "lib_old.yaml")
    ], f"the stale file is reported: {added}"
    text = (tmp_path / "lib.uml-report.txt").read_text(encoding="utf-8")
    assert "stale-file\tlib_old.yaml\t" in text, f"the report file names it: {text!r}"


def test_a_written_file_is_not_stale_on_a_rerun(tmp_path: Path) -> None:
    write(_schemas(), _report(), tmp_path, ROOT)

    assert write(_schemas(), _report(), tmp_path, ROOT) == [], "the files it wrote are not stale"


def test_a_file_outside_the_root_pattern_is_untouched_and_not_reported(tmp_path: Path) -> None:
    (tmp_path / "notes.yaml").write_text("keep: me\n", encoding="utf-8")
    (tmp_path / "other_x.yaml").write_text("keep: me\n", encoding="utf-8")

    added = write(_schemas(), _report(), tmp_path, ROOT)

    report = (tmp_path / "lib.uml-report.txt").read_text(encoding="utf-8")
    assert added == [], f"no file is reported stale: {added}"
    assert (tmp_path / "notes.yaml").read_text(encoding="utf-8") == "keep: me\n", "notes kept"
    assert "notes.yaml" not in report, "notes.yaml is not in the report"
    assert "other_x.yaml" not in report, "other_x.yaml is not in the report"


def test_the_temporary_folder_is_gone_afterwards(tmp_path: Path) -> None:
    out = tmp_path / "out"

    write(_schemas(), _report(), out, ROOT)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["out"], "no temp folder is left"


def test_an_output_folder_that_does_not_exist_is_created(tmp_path: Path) -> None:
    out = tmp_path / "deep" / "out"

    write(_schemas(), [], out, ROOT)

    assert (out / "lib.uml-report.txt").read_text(encoding="utf-8") == "", "an empty report file"


def test_problems_print_sorted_one_line_each() -> None:
    problems = [
        CheckProblem(rule="no_rule", element="lib:B", message="second"),
        CheckProblem(rule="class_iri", element="lib:A", message="first"),
    ]

    assert format_problems(problems) == "\n".join(
        sorted(format_problem(problem) for problem in problems)
    ), "one line per problem, sorted"


# --- the roles file (PD-3, PD-4, PD-6, PD-8) -----------------------------------------------------


def _role(object_id: int, name: str, role: str, level: str, actions: str):
    return object_(
        object_id,
        name,
        ROLE_DEFINITION,
        ("role", role),
        ("level", level),
        ("actions", actions),
    )


def _drawn(*objects) -> Converted:
    uml = model(
        klass(BOOK, "lib:Book"), klass(ROLE_DEFINITION, "rp:RoleDefinition"), objects=objects
    )
    converted = run(uml, root_name=ROOT)
    assert converted.problems == [], converted.problem_texts()
    return converted


def _two_roles() -> Converted:
    return _drawn(
        _role(1, "writer", "writer", "tenant", "read, modify"),
        _role(2, "reader at tenant", "reader", "tenant", "read"),
        _role(3, "reader at aggregate", "reader", "aggregate", "read"),
    )


def _write(converted: Converted, out: Path, report: list[ReportLine] | None = None):
    return write(
        list(converted.schemas.values()),
        converted.report if report is None else report,
        out,
        ROOT,
        files=converted.files,
    )


def test_the_roles_file_is_written_sorted_and_read_back_by_the_loader(tmp_path: Path) -> None:
    converted = _two_roles()

    _write(converted, tmp_path)

    expected = [
        {"role": "reader", "level": "aggregate", "actions": ["read"]},
        {"role": "reader", "level": "tenant", "actions": ["read"]},
        {"role": "writer", "level": "tenant", "actions": ["read", "modify"]},
    ]
    text = (tmp_path / ROLES_FILE).read_text(encoding="utf-8")
    assert text == yaml.safe_dump(expected, sort_keys=False, allow_unicode=True, width=100), text
    loaded = [(d.role, d.level, d.actions) for d in load_role_definitions(tmp_path / ROLES_FILE)]
    assert loaded == [(e["role"], e["level"], e["actions"]) for e in expected], loaded


def test_no_role_object_writes_no_roles_file_and_no_files_are_returned(tmp_path: Path) -> None:
    converted = _drawn()

    _write(converted, tmp_path)

    assert converted.files == {}, "nothing drawn, nothing to write"
    assert not (tmp_path / ROLES_FILE).exists(), "no roles file"


def test_a_second_run_with_roles_is_byte_identical(tmp_path: Path) -> None:
    _write(_two_roles(), tmp_path)
    first = {file.name: file.read_bytes() for file in sorted(tmp_path.iterdir())}

    _write(_two_roles(), tmp_path)

    assert {file.name: file.read_bytes() for file in sorted(tmp_path.iterdir())} == first
    assert ROLES_FILE in first, "the roles file is among them"


def test_a_stray_roles_file_is_left_unreported_when_no_role_is_drawn(tmp_path: Path) -> None:
    (tmp_path / "hand.roles.yaml").write_text("- role: x\n", encoding="utf-8")
    plain = _drawn()

    added = _write(plain, tmp_path)

    assert added == [], f"a hand-written roles file is not stale: {added}"
    assert "stale-file" not in (tmp_path / "lib.uml-report.txt").read_text(encoding="utf-8")
    assert (tmp_path / "hand.roles.yaml").read_text(encoding="utf-8") == "- role: x\n", "kept"


def test_another_roots_roles_file_is_stale_when_roles_are_drawn(tmp_path: Path) -> None:
    (tmp_path / "old.roles.yaml").write_text("[]\n", encoding="utf-8")

    added = _write(_two_roles(), tmp_path)

    assert [(line.report_kind, line.element) for line in added] == [
        (ReportKind.STALE_FILE, "old.roles.yaml")
    ], f"the other root's file is reported: {added}"
    assert (tmp_path / "old.roles.yaml").exists(), "and kept"
    assert "stale-file\told.roles.yaml\t" in (tmp_path / "lib.uml-report.txt").read_text(
        encoding="utf-8"
    )


def test_the_roles_file_this_run_writes_is_not_stale_on_a_rerun(tmp_path: Path) -> None:
    _write(_two_roles(), tmp_path)

    assert _write(_two_roles(), tmp_path) == [], "its own roles file is not stale"


def test_a_staged_file_the_loader_refuses_moves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(path: Path):
        raise InvalidRoleDefinition(f"{path.name}: entry 1: refused")

    monkeypatch.setattr(write_module, "load_role_definitions", refuse)
    out = tmp_path / "out"
    out.mkdir()
    (out / "lib_main.yaml").write_text("kept: yes\n", encoding="utf-8")

    with pytest.raises(StagedFileRefused, match="lib.roles.yaml: entry 1: refused"):
        _write(_two_roles(), out)

    assert sorted(file.name for file in out.iterdir()) == ["lib_main.yaml"], "nothing was moved"
    assert (out / "lib_main.yaml").read_text(encoding="utf-8") == "kept: yes\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["out"], "no temp folder is left"
