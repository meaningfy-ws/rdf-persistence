"""Adversarial probes of the writer (PD-3, DEC-4, I-2): every failure leaves a re-runnable ``--out``."""

import errno
import os
import stat
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.linkml_model.meta import SchemaDefinition

from rdf_persistence_generation.exceptions import OutputError
from rdf_persistence_generation.generated.rp_generation import ReportKind
from rdf_persistence_generation.uml.write import STAGING_PREFIX, write
from tests.generator.unit.test_uml_cli import PREFIX, build_library, run
from tests.generator.unit.test_uml_write import ROOT, _loan, _report, _schemas, _write

REPORT = f"{ROOT}.uml-report.txt"


def _tree(out: Path) -> dict[str, bytes]:
    """Every file under ``out`` by relative path, staging folders included."""
    return {
        file.relative_to(out).as_posix(): file.read_bytes()
        for file in sorted(out.rglob("*"))
        if file.is_file()
    }


def _clean_tree(tmp_path: Path) -> dict[str, bytes]:
    clean = tmp_path / "clean"
    _write(_loan(), clean)
    return _tree(clean)


def _recording_move() -> tuple[Callable[[Path, Path], None], list[Path]]:
    targets: list[Path] = []

    def move(source: Path, target: Path) -> None:
        targets.append(target)
        os.replace(source, target)

    return move, targets


def _failing_move(
    fail_on: Callable[[int, Path], bool], code: int = errno.ENOSPC
) -> Callable[[Path, Path], None]:
    """A move that fails like ``os.replace``: the error names the staged source."""
    count = 0

    def move(source: Path, target: Path) -> None:
        nonlocal count
        count += 1
        if fail_on(count - 1, target):
            raise OSError(code, os.strerror(code), str(source), None, str(target))
        os.replace(source, target)

    return move


def _no_staging(out: Path) -> bool:
    return not [path for path in out.iterdir() if path.name.startswith(STAGING_PREFIX)]


@pytest.fixture
def previous_run(tmp_path: Path) -> Path:
    """An ``out`` holding an earlier, different run, with its report."""
    out = tmp_path / "out"
    converted = _loan()
    write(list(converted.schemas.values()), [], out, ROOT, files=converted.files)
    assert (out / REPORT).exists(), "the earlier run left its report"
    return out


@pytest.fixture
def read_only(tmp_path: Path) -> Iterator[Path]:
    out = tmp_path / "out"
    out.mkdir()
    out.chmod(stat.S_IRUSR | stat.S_IXUSR)
    yield out
    out.chmod(stat.S_IRWXU)


# --- a failure on the moves (matrix: disk error while moving, EXDEV; G-3, I-2) ------------------


@pytest.mark.parametrize("position", [0, 1, -2, -1], ids=["first", "second", "last-file", "report"])
def test_a_move_failing_at_a_position_leaves_no_report_names_the_target_and_reruns_clean(
    tmp_path: Path, previous_run: Path, position: int
) -> None:
    """probe of PD-3 'Disk error while moving' (first, second, last non-report, report moves)."""
    expected = _clean_tree(tmp_path)
    move, targets = _recording_move()
    write_args = _loan()
    write(
        list(write_args.schemas.values()),
        write_args.report,
        tmp_path / "count",
        ROOT,
        files=write_args.files,
        move=move,
    )
    failing = targets[position].relative_to(tmp_path / "count")
    out = previous_run

    with pytest.raises(OutputError) as raised:
        write(
            list(write_args.schemas.values()),
            write_args.report,
            out,
            ROOT,
            files=write_args.files,
            move=_failing_move(lambda _, target: target.relative_to(out) == failing),
        )

    assert raised.value.path == out / failing, f"names the target, not the source: {raised.value}"
    assert not (out / REPORT).exists(), "no report after an interrupted write (G-3)"
    assert _no_staging(out), "the staging folder is removed"
    _write(_loan(), out)
    assert {k: v for k, v in _tree(out).items() if k in expected} == expected, (
        "a re-run writes the bytes of a clean run"
    )


def test_files_moved_before_the_failure_stay_and_the_later_ones_are_absent(tmp_path: Path) -> None:
    """probe of PD-3 'files moved so far stay'."""
    converted = _loan()
    out = tmp_path / "out"

    with pytest.raises(OutputError):
        write(
            list(converted.schemas.values()),
            converted.report,
            out,
            ROOT,
            files=converted.files,
            move=_failing_move(lambda index, _: index == 2),
        )

    names = sorted(_tree(out))
    assert len(names) == 2, f"exactly the two files moved before the failure stay: {names}"


def test_a_cross_device_error_on_a_subfolder_is_an_output_error_naming_the_target(
    tmp_path: Path,
) -> None:
    """probe of PD-3 'A subfolder of --out on another filesystem' (EXDEV)."""
    converted = _loan()
    out = tmp_path / "out"

    with pytest.raises(OutputError) as raised:
        write(
            list(converted.schemas.values()),
            converted.report,
            out,
            ROOT,
            files=converted.files,
            move=_failing_move(lambda _, target: target.parent.name == "workflows", errno.EXDEV),
        )

    assert raised.value.path == out / "workflows" / "loan.workflow.yaml", raised.value.path
    assert raised.value.reason == os.strerror(errno.EXDEV), raised.value.reason
    assert not (out / REPORT).exists(), "no report"


# --- a failure while dumping or staging (matrix: disk full or error while dumping or staging) ----


def test_a_schema_that_cannot_be_dumped_changes_nothing_and_keeps_the_old_report(
    previous_run: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """probe of PD-3 'Disk full or error while dumping'."""
    before = _tree(previous_run)

    def full(schema: SchemaDefinition, to_file: str) -> None:
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC), to_file)

    monkeypatch.setattr(yaml_dumper, "dump", full)  # X3: a full disk no real folder gives here

    with pytest.raises(OutputError) as raised:
        write(_schemas(), _report(), previous_run, ROOT)

    assert raised.value.path.name == "lib_books.yaml", f"names the staged file: {raised.value.path}"
    assert _tree(previous_run) == before, "--out is unchanged, the old report included"
    assert _no_staging(previous_run), "the staging folder is removed"


def test_an_other_file_that_cannot_be_staged_changes_nothing(previous_run: Path) -> None:
    """probe of PD-3 'error while staging' (a file path under a name the schemas already used)."""
    before = _tree(previous_run)

    with pytest.raises(OutputError):
        write(_schemas(), _report(), previous_run, ROOT, files={"lib_books.yaml/x.txt": "x"})

    assert _tree(previous_run) == before, "--out is unchanged"
    assert _no_staging(previous_run), "the staging folder is removed"


def test_a_stale_file_search_that_raises_is_an_output_error_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """probe of PD-3 'Any OSError raised anywhere in write (the stale-file globs included)'."""
    out = tmp_path / "out"
    out.mkdir()

    def broken(self: Path, pattern: str):
        raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(self / "locked"))

    monkeypatch.setattr(Path, "glob", broken)  # X3: a listing failure no real folder gives here

    with pytest.raises(OutputError) as raised:
        write(_schemas(), _report(), out, ROOT)

    assert raised.value.path == out / "locked", f"names what the failing call named: {raised.value}"
    assert list(out.iterdir()) == [], "nothing was written"


# --- an --out that cannot be used (matrix: --out cannot be created, is a file, or not writable) --


def test_an_out_inside_a_file_is_an_output_error_naming_it(tmp_path: Path) -> None:
    """probe of PD-3 '--out cannot be created' (a parent is a file)."""
    (tmp_path / "file").write_text("x", encoding="utf-8")
    out = tmp_path / "file" / "sub"

    with pytest.raises(OutputError) as raised:
        write(_schemas(), _report(), out, ROOT)

    assert raised.value.path == out, f"names --out: {raised.value.path}"


def test_a_dangling_symlink_as_out_is_an_output_error(tmp_path: Path) -> None:
    """probe of PD-3 '--out cannot be created' (a symlink to nowhere)."""
    out = tmp_path / "out"
    out.symlink_to(tmp_path / "nowhere")

    with pytest.raises(OutputError) as raised:
        write(_schemas(), _report(), out, ROOT)

    assert raised.value.path == out, f"names --out: {raised.value.path}"
    assert not (tmp_path / "nowhere").exists(), "nothing created behind the link"


def test_a_symlink_to_a_folder_as_out_is_written_through_and_reruns_identically(
    tmp_path: Path,
) -> None:
    """probe of PD-3 (--out a symlink to a folder)."""
    real = tmp_path / "real"
    real.mkdir()
    out = tmp_path / "link"
    out.symlink_to(real, target_is_directory=True)
    write(_schemas(), _report(), out, ROOT)
    first = _tree(real)

    added = write(_schemas(), _report(), out, ROOT)

    assert sorted(first) == [REPORT, "lib_books.yaml", "lib_shelves.yaml"], sorted(first)
    assert (_tree(real), added) == (first, []), "the second run changes no byte and finds no stale"


def test_a_folder_in_the_place_of_the_report_is_an_output_error_and_changes_nothing(
    tmp_path: Path,
) -> None:
    """probe of PD-3 step 4 (the old report cannot be deleted)."""
    out = tmp_path / "out"
    (out / REPORT).mkdir(parents=True)
    (out / "lib_books.yaml").write_text("old: yes\n", encoding="utf-8")

    with pytest.raises(OutputError) as raised:
        write(_schemas(), _report(), out, ROOT)

    assert raised.value.path == out / REPORT, f"names the report: {raised.value.path}"
    assert (out / "lib_books.yaml").read_text(encoding="utf-8") == "old: yes\n", "no file moved"
    assert _no_staging(out), "the staging folder is removed"


def test_a_read_only_out_is_an_output_error_naming_out(read_only: Path) -> None:
    """found unwritable-out-names-staging: row 1 says <out>; the error names ``out/.uml-write-*``."""
    with pytest.raises(OutputError) as raised:
        write(_schemas(), _report(), read_only, ROOT)

    assert raised.value.path == read_only, f"names --out: {raised.value.path}"
    assert list(read_only.iterdir()) == [], "nothing was written"


def test_the_command_exits_two_with_one_line_for_a_read_only_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """found unwritable-out-names-staging: the command line names a removed staging folder."""
    builder, _ = build_library(tmp_path)
    qea = builder.finish()
    out = tmp_path / "out"
    out.mkdir()
    out.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        code, lines = run(capsys, tmp_path, qea)
    finally:
        out.chmod(stat.S_IRWXU)

    assert (code, lines) == (2, [f"{PREFIX}cannot write {out}: Permission denied"]), (code, lines)


# --- what an earlier or interrupted run left (matrix: a run was killed mid-write; I-2) ----------


def test_a_left_staging_file_is_neither_reported_nor_deleted(tmp_path: Path) -> None:
    """probe of PD-3 'left staging': a plain file with the staging name is not a folder."""
    left = tmp_path / f"{STAGING_PREFIX}file"
    left.write_text("mine", encoding="utf-8")

    added = write(_schemas(), _report(), tmp_path, ROOT)

    assert added == [], f"only folders are reported: {added}"
    assert left.read_text(encoding="utf-8") == "mine", "and the file is kept"


def test_two_left_staging_folders_are_both_reported_in_order_and_kept(tmp_path: Path) -> None:
    """probe of PD-3 'A run was killed mid-write' (two of them)."""
    for suffix in ("b", "a"):
        (tmp_path / f"{STAGING_PREFIX}{suffix}").mkdir()

    added = write(_schemas(), _report(), tmp_path, ROOT)

    assert [(line.report_kind, line.element) for line in added] == [
        (ReportKind.STALE_FILE, f"{STAGING_PREFIX}a"),
        (ReportKind.STALE_FILE, f"{STAGING_PREFIX}b"),
    ], f"both, sorted: {added}"
    assert sorted(path.name for path in tmp_path.glob(f"{STAGING_PREFIX}*")) == [
        f"{STAGING_PREFIX}a",
        f"{STAGING_PREFIX}b",
    ], "both kept, and none of the run's own left behind"


def test_the_report_file_lists_the_left_folder_and_the_stale_file_once_each(
    tmp_path: Path,
) -> None:
    """probe of PD-3 (the run never reports its own staging folder; the file names them)."""
    (tmp_path / f"{STAGING_PREFIX}old").mkdir()
    (tmp_path / "lib_gone.yaml").write_text("x: 1\n", encoding="utf-8")

    write(_schemas(), [], tmp_path, ROOT)

    lines = (tmp_path / REPORT).read_text(encoding="utf-8").splitlines()
    assert sorted(line.split("\t")[1] for line in lines) == sorted(
        [f"{STAGING_PREFIX}old", "lib_gone.yaml"]
    ), f"one line for each, none for the run's own staging: {lines}"


def test_a_previous_report_alone_is_replaced_and_the_run_equals_a_clean_run(
    tmp_path: Path,
) -> None:
    """probe of I-2 (a previous report but no other file)."""
    out = tmp_path / "out"
    out.mkdir()
    (out / REPORT).write_text("not-generated\told\tx\n", encoding="utf-8")
    clean = tmp_path / "clean"
    write(_schemas(), _report(), clean, ROOT)

    write(_schemas(), _report(), out, ROOT)

    assert _tree(out) == _tree(clean), "the old report leaves no trace"


def test_a_rerun_over_a_different_earlier_run_rewrites_every_written_file(tmp_path: Path) -> None:
    """probe of I-2: a run's own files are overwritten, whatever they held."""
    out = tmp_path / "out"
    out.mkdir()
    for name in ("lib_books.yaml", "lib_shelves.yaml"):
        (out / name).write_text("garbage: true\n", encoding="utf-8")
    clean = tmp_path / "clean"
    write(_schemas(), _report(), clean, ROOT)

    write(_schemas(), _report(), out, ROOT)

    assert _tree(out) == _tree(clean), "byte-identical to a clean run"


def test_a_failed_run_then_a_rerun_with_a_left_stale_file_reports_it_in_the_report(
    tmp_path: Path,
) -> None:
    """probe of I-2: the file a failed run moved is not later reported as stale."""
    out = tmp_path / "out"
    with pytest.raises(OutputError):
        write(_schemas(), _report(), out, ROOT, move=_failing_move(lambda i, _: i == 1))

    added = write(_schemas(), _report(), out, ROOT)

    assert added == [], f"the file the failed run moved is this run's own: {added}"
