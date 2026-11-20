"""TC-10 (write part): the files, the sorted report, the stale-file line, the byte-identical rerun (PD-22, I-2)."""

from pathlib import Path

from linkml_runtime.linkml_model.meta import SchemaDefinition

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    ReportKind,
    ReportLine,
)
from rdf_persistence_generation.problems import format_problem, format_problems
from rdf_persistence_generation.uml.write import write

ROOT = "lib"


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
