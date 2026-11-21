"""The scenario-map refresher drops rows of vanished tests and lists unmapped ids (PD-16)."""

import subprocess
from pathlib import Path

import pytest

from tests.audit import refresh_map
from tests.audit.refresh_map import (
    EXIT_COLLECTION_FAILED,
    EXIT_MALFORMED_MAP,
    EXIT_NEW_IDS,
    EXIT_OK,
    EXIT_REFUSED,
    function_ids,
    main,
    refresh,
    renames,
)

HEADER = "test,level,capability,requirement,scenario,confidence,evidence"
KEPT_FIRST = "tests/unit/test_a.py::test_kept_first,scenario,cap,Req A,sc,high,name"
GONE = "tests/unit/test_a.py::test_gone,requirement,cap,Req B,,high,name"
KEPT_LAST = 'tests/unit/test_b.py::test_param,scenario,cap,Req C,sc,high,"name; code (x, y)"'
COLLECTED = """\
tests/unit/test_a.py::test_kept_first
tests/unit/test_b.py::test_param[one]
tests/unit/test_b.py::test_param[two-2]
tests/unit/test_b.py::TestKlass::test_new

3 tests collected in 0.10s
"""


def _map_text(*rows: str) -> str:
    return "\n".join((HEADER, *rows)) + "\n"


def test_a_parametrised_id_collapses_to_its_function() -> None:
    ids = function_ids(COLLECTED)

    assert ids == {
        "tests/unit/test_a.py::test_kept_first",
        "tests/unit/test_b.py::test_param",
        "tests/unit/test_b.py::TestKlass::test_new",
    }, "case suffixes and non-node lines must not leave the id set"


def test_refresh_removes_vanished_rows_and_keeps_the_rest_in_order() -> None:
    result = refresh(_map_text(KEPT_FIRST, GONE, KEPT_LAST), function_ids(COLLECTED))

    assert result.removed == ["tests/unit/test_a.py::test_gone"], "the vanished row is reported"
    assert result.text == _map_text(KEPT_FIRST, KEPT_LAST), (
        "kept rows are unchanged, quoting included, and in their order"
    )


def test_refresh_lists_collected_ids_that_have_no_row() -> None:
    result = refresh(_map_text(KEPT_FIRST, GONE, KEPT_LAST), function_ids(COLLECTED))

    assert result.new == ["tests/unit/test_b.py::TestKlass::test_new"], "unmapped id is reported"


def test_refresh_of_a_complete_map_changes_nothing() -> None:
    text = _map_text(KEPT_FIRST, KEPT_LAST)

    result = refresh(
        text, {"tests/unit/test_a.py::test_kept_first", "tests/unit/test_b.py::test_param"}
    )

    assert (result.text, result.removed, result.new) == (text, [], []), "nothing to remove or map"


PADDING_IDS = tuple(f"tests/unit/test_pad.py::test_pad_{n}" for n in range(4))
PADDING_ROWS = tuple(f"{test_id},scenario,cap,Req P,sc,high,name" for test_id in PADDING_IDS)
PADDING_COLLECTED = "".join(f"{test_id}\n" for test_id in PADDING_IDS)


@pytest.mark.parametrize(
    ("collected", "code"),
    [
        ("tests/unit/test_a.py::test_kept_first\n", EXIT_OK),
        (COLLECTED, EXIT_NEW_IDS),
    ],
    ids=["no-new-ids", "new-ids"],
)
def test_main_exits_one_only_when_ids_are_unmapped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], collected: str, code: int
) -> None:
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(_map_text(KEPT_FIRST, GONE, *PADDING_ROWS))
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(collected + PADDING_COLLECTED)

    status = main(["--map", str(csv_path), "--collect", str(collect_path)])

    out = capsys.readouterr().out
    assert status == code, "exit code follows the presence of unmapped ids"
    assert csv_path.read_text() == _map_text(KEPT_FIRST, *PADDING_ROWS), (
        "the map is rewritten without the gone row"
    )
    assert "test_gone" in out, "removed ids are printed"
    assert ("TestKlass::test_new" in out) is (code == EXIT_NEW_IDS), "new ids are printed"


def test_refresh_keeps_the_line_endings_of_the_map() -> None:
    crlf = _map_text(KEPT_FIRST, GONE).replace("\n", "\r\n")

    result = refresh(crlf, {"tests/unit/test_a.py::test_kept_first"})

    assert result.text == _map_text(KEPT_FIRST).replace("\n", "\r\n"), (
        "CRLF must survive the rewrite"
    )


COLLECT_ERROR_OUTPUT = "ERROR: file or directory not found: tests\n\nno tests ran in 0.01s\n"


def _run_main(tmp_path: Path, rows: tuple[str, ...], collected: str) -> tuple[int, Path, str]:
    csv_path = tmp_path / "map.csv"
    original = _map_text(*rows)
    csv_path.write_text(original)
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(collected)
    status = main(["--map", str(csv_path), "--collect", str(collect_path)])
    return status, csv_path, original


def test_a_collection_with_an_error_and_no_node_ids_leaves_the_map_untouched(
    tmp_path: Path,
) -> None:
    status, csv_path, original = _run_main(
        tmp_path, (KEPT_FIRST, GONE, KEPT_LAST), COLLECT_ERROR_OUTPUT
    )

    assert status == EXIT_COLLECTION_FAILED, "a failed collection must exit non-zero"
    assert csv_path.read_text() == original, "a failed collection must not erase the map"


def test_more_than_a_fifth_of_the_rows_going_refuses_the_rewrite(tmp_path: Path) -> None:
    status, csv_path, original = _run_main(
        tmp_path, (KEPT_FIRST, GONE, KEPT_LAST), "tests/unit/test_a.py::test_kept_first\n"
    )

    assert status == EXIT_REFUSED, "removing 2 of 3 rows must be refused, apart from a failed run"
    assert csv_path.read_text() == original, "a refused rewrite must leave the map as it was"


def test_the_two_ways_to_keep_the_map_have_their_own_exit_codes() -> None:
    codes = {EXIT_OK, EXIT_NEW_IDS, EXIT_COLLECTION_FAILED, EXIT_REFUSED, EXIT_MALFORMED_MAP}

    assert len(codes) == 5, "each outcome needs its own status for the caller to tell them apart"


@pytest.mark.parametrize(
    "map_text",
    [
        "",
        "level,capability\nscenario,cap\n",
        f"{HEADER}\ntests/unit/test_a.py::test_kept_first,scenario\n",
    ],
    ids=["empty", "no-test-column", "short-row"],
)
def test_a_malformed_map_exits_with_a_message_and_stays_as_it_was(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], map_text: str
) -> None:
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(map_text)
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(COLLECTED)

    status = main(["--map", str(csv_path), "--collect", str(collect_path)])

    assert status == EXIT_MALFORMED_MAP, "a malformed map must not end in a traceback"
    assert "malformed" in capsys.readouterr().out, "the message says what is wrong"
    assert csv_path.read_text() == map_text, "a malformed map is left as it was"


OLD_FILE = "tests/unit/old/test_m.py"
NEW_FILE = "tests/unit/new/test_m.py"
MOVED_ROW = f"{OLD_FILE}::test_moved,scenario,cap,Req M,sc,high,name"
MOVED_GONE_ROW = f"{OLD_FILE}::test_dropped,requirement,cap,Req N,,high,name"
MOVED_COLLECTED = f"{NEW_FILE}::test_moved\n"


def _git_stdout(monkeypatch: pytest.MonkeyPatch, stdout: str, returncode: int = 0) -> list[list]:
    """Make the refresher's `git diff` answer `stdout`; return the commands it ran."""
    calls: list[list] = []

    def fake_run(command: list, **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, returncode, stdout, "fatal: bad revision")

    monkeypatch.setattr(refresh_map.subprocess, "run", fake_run)
    return calls


@pytest.fixture(autouse=True)
def _no_renames(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unless a test says otherwise, git reports no renames, whatever the checkout holds."""
    _git_stdout(monkeypatch, "")


def test_a_renamed_file_re_keys_its_rows_to_the_new_path() -> None:
    result = refresh(_map_text(MOVED_ROW), {f"{NEW_FILE}::test_moved"}, moves={OLD_FILE: NEW_FILE})

    assert result.text == _map_text(MOVED_ROW.replace(OLD_FILE, NEW_FILE)), (
        "the row keeps its fields and takes the new path"
    )
    assert result.rekeyed == [(f"{OLD_FILE}::test_moved", f"{NEW_FILE}::test_moved")], (
        "the re-keyed row is reported old to new"
    )
    assert result.removed == [], "a re-keyed row is not a removed one"
    assert result.new == [], "the moved test is mapped, not new"


def test_a_renamed_file_whose_function_is_gone_drops_the_row() -> None:
    result = refresh(
        _map_text(MOVED_ROW, MOVED_GONE_ROW),
        {f"{NEW_FILE}::test_moved"},
        moves={OLD_FILE: NEW_FILE},
    )

    assert result.removed == [f"{OLD_FILE}::test_dropped"], "no function at the new path: dropped"
    assert result.text == _map_text(MOVED_ROW.replace(OLD_FILE, NEW_FILE)), "the other row moved"


def test_a_folder_prefix_move_re_keys_every_file_under_it() -> None:
    nested = "tests/unit/old/sub/test_n.py::test_deep,scenario,cap,Req D,sc,high,name"

    result = refresh(
        _map_text(MOVED_ROW, nested),
        {f"{NEW_FILE}::test_moved", "tests/unit/new/sub/test_n.py::test_deep"},
        moves={"tests/unit/old": "tests/unit/new"},
    )

    assert [new for _, new in result.rekeyed] == [
        f"{NEW_FILE}::test_moved",
        "tests/unit/new/sub/test_n.py::test_deep",
    ], "a folder prefix applies to the files below it"


def test_a_folder_prefix_does_not_match_a_sibling_sharing_the_text() -> None:
    sibling = "tests/unit/older/test_s.py::test_s,scenario,cap,Req S,sc,high,name"

    result = refresh(
        _map_text(sibling),
        {"tests/unit/newer/test_s.py::test_s"},
        moves={"tests/unit/old": "tests/unit/new"},
    )

    assert result.rekeyed == [], "`old` is a folder, not a text prefix of `older`"
    assert result.removed == ["tests/unit/older/test_s.py::test_s"], "the sibling row is dropped"


def test_rows_re_keyed_by_a_move_do_not_count_towards_the_twenty_percent_share(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(_map_text(MOVED_ROW, *PADDING_ROWS))
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(MOVED_COLLECTED + PADDING_COLLECTED)

    status = main(
        [
            "--map",
            str(csv_path),
            "--collect",
            str(collect_path),
            "--moved",
            f"{OLD_FILE}={NEW_FILE}",
        ]
    )

    out = capsys.readouterr().out
    assert status == EXIT_OK, "one of five rows moving is no refusal"
    assert csv_path.read_text() == _map_text(MOVED_ROW.replace(OLD_FILE, NEW_FILE), *PADDING_ROWS)
    assert "Re-keyed rows (1):" in out, "the output lists the re-keyed rows"
    assert f"{OLD_FILE}::test_moved -> {NEW_FILE}::test_moved" in out, "each as old -> new"


def test_without_the_move_the_same_rows_are_refused(tmp_path: Path) -> None:
    csv_path = tmp_path / "map.csv"
    rows = (MOVED_ROW, MOVED_GONE_ROW, *PADDING_ROWS[:1])
    csv_path.write_text(_map_text(*rows))
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(MOVED_COLLECTED + PADDING_COLLECTED)

    status = main(["--map", str(csv_path), "--collect", str(collect_path)])

    assert status == EXIT_REFUSED, "control: dropped rows still count towards the share"


def test_git_renames_re_key_rows_and_the_base_is_passed_to_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _git_stdout(
        monkeypatch,
        f"R100\t{OLD_FILE}\t{NEW_FILE}\nM\ttests/unit/other.py\nA\ttests/unit/added.py\n",
    )
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(_map_text(MOVED_ROW, *PADDING_ROWS))
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(MOVED_COLLECTED + PADDING_COLLECTED)

    status = main(
        ["--map", str(csv_path), "--collect", str(collect_path), "--base", "origin/develop"]
    )

    assert status == EXIT_OK, "the rename read from git moves the row"
    assert csv_path.read_text() == _map_text(MOVED_ROW.replace(OLD_FILE, NEW_FILE), *PADDING_ROWS)
    assert calls == [["git", "diff", "--name-status", "-M", "origin/develop", "--", "tests"]], (
        "git is asked for the renames under tests against the base"
    )


def test_renames_parses_only_rename_lines_with_a_score() -> None:
    output = f"R087\t{OLD_FILE}\t{NEW_FILE}\nM\ta.py\nD\tb.py\nC100\tc.py\td.py\n"

    assert renames(output) == {OLD_FILE: NEW_FILE}, "only R<score> lines are moves"


@pytest.mark.parametrize("failure", ["missing", "bad-ref"])
def test_git_unavailable_behaves_as_before_with_a_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    if failure == "missing":

        def no_git(command: list, **_: object) -> None:
            raise FileNotFoundError("git")

        monkeypatch.setattr(refresh_map.subprocess, "run", no_git)
    else:
        _git_stdout(monkeypatch, "", returncode=128)
    csv_path = tmp_path / "map.csv"
    csv_path.write_text(_map_text(MOVED_ROW, *PADDING_ROWS))
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text(PADDING_COLLECTED)

    status = main(["--map", str(csv_path), "--collect", str(collect_path)])

    out = capsys.readouterr().out
    assert "Warning: no moves from git" in out, "the warning line says moves were not read"
    assert status == EXIT_OK, "the run goes on as it did before moves"
    assert csv_path.read_text() == _map_text(*PADDING_ROWS), "the vanished rows are dropped"


def test_a_moved_argument_without_an_equals_sign_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        main(["--moved", "no-equals-sign"])


def test_a_failed_replace_leaves_the_map_whole_and_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = tmp_path / "map.csv"
    original = _map_text(KEPT_FIRST, GONE, *PADDING_ROWS)
    csv_path.write_text(original)
    collect_path = tmp_path / "collect.txt"
    collect_path.write_text("tests/unit/test_a.py::test_kept_first\n" + PADDING_COLLECTED)

    def refuse(self: Path, target: Path) -> Path:
        raise OSError("disk gone")

    monkeypatch.setattr(Path, "replace", refuse)

    with pytest.raises(OSError, match="disk gone"):
        main(["--map", str(csv_path), "--collect", str(collect_path)])

    assert csv_path.read_text() == original, "the map is replaced whole or not at all"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["collect.txt", "map.csv"], (
        "the temporary file is removed when the replace fails"
    )
